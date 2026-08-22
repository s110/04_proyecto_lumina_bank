#!/usr/bin/env python3
"""Lumina Bank - arnes de medicion de latencia y throughput.

Mide la ruta de decision de fraude bajo carga sostenida y deja un artefacto
JSON atribuible: que se midio, contra que revision, con que configuracion.

Dos decisiones de diseno que son la diferencia entre un numero defendible y
uno que se cae en la primera repregunta:

1. LAZO ABIERTO (open loop). Un generador de carga en lazo cerrado espera la
   respuesta antes de mandar la siguiente peticion, asi que cuando el servidor
   se degrada el generador manda menos carga y el percentil sale bonito. Este
   manda a una tasa fija pase lo que pase.

2. LATENCIA CONTRA EL INSTANTE PREVISTO, no contra el instante real de envio.
   Si el emisor se atrasa porque el pool esta saturado, esa espera es latencia
   que el usuario sufre. Descontarla es "coordinated omission" y es la forma
   mas comun de publicar un p95 que no existe. Aqui se reportan las dos y la
   brecha entre ellas es, por si sola, una senal de saturacion.

Uso:
    python bench/loadtest.py --url https://<servicio>/score --rps 500 --seconds 120
    python bench/loadtest.py --url https://<servicio>/score --rps 500 --seconds 120 \
        --ramp 100,250,500,1000,2000,5000 --step-seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("falta httpx: pip install httpx")

BANKS = [
    "banco-central-datalandia", "banco-norte-metropolitano",
    "banco-sur-cooperativo", "banco-este-comercial",
    "banco-oeste-industrial", "banco-union-popular",
    "banco-progreso-digital", "banco-herencia-nacional",
    "banco-innovacion-fintech", "banco-solidario-regional",
    "banco-mercantil-datalandia", "banco-federal-integrado",
]
TX_TYPES = ["TRANSFER", "PAYMENT", "WITHDRAWAL", "DEPOSIT"]
CHANNELS = ["APP", "ATM", "BRANCH", "CORRESPONDENT"]


def transaction(rng: random.Random) -> dict:
    """Una transaccion sintetica con la forma que valida el servicio de ingesta."""
    return {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": f"CUST-{rng.randint(1, 9_000_000):08d}",
        "bank_entity": rng.choice(BANKS),
        "transaction_type": rng.choice(TX_TYPES),
        "channel": rng.choice(CHANNELS),
        # Cola pesada a proposito: el 2% son montos grandes, que es donde el
        # modelo de fraude tiene mas trabajo y donde vive la cola de latencia.
        "amount": round(rng.lognormvariate(4.2, 1.1) * (40 if rng.random() < 0.02 else 1), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@dataclass
class Sample:
    intended_ns: int
    sent_ns: int
    done_ns: int
    status: int
    error: str | None = None

    @property
    def service_ms(self) -> float:
        """Lo que tardo el servidor, desde que salio la peticion."""
        return (self.done_ns - self.sent_ns) / 1e6

    @property
    def observed_ms(self) -> float:
        """Lo que espero el usuario: incluye el atraso del propio emisor."""
        return (self.done_ns - self.intended_ns) / 1e6


@dataclass
class Stage:
    rps: int
    seconds: int
    samples: list[Sample] = field(default_factory=list)


def percentiles(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)

    def pct(p: float) -> float:
        # Percentil por rango mas cercano: sin interpolar, para que p99 con
        # pocas muestras sea una observacion real y no un promedio inventado.
        idx = min(len(ordered) - 1, max(0, round(p / 100 * len(ordered) + 0.5) - 1))
        return round(ordered[idx], 2)

    return {
        "n": len(ordered),
        "min": round(ordered[0], 2),
        "p50": pct(50), "p90": pct(90), "p95": pct(95), "p99": pct(99),
        "max": round(ordered[-1], 2),
        "mean": round(statistics.fmean(ordered), 2),
    }


async def run_stage(client: httpx.AsyncClient, url: str, stage: Stage,
                    rng: random.Random, timeout_s: float) -> None:
    """Dispara a tasa fija durante `seconds`, sin esperar a las respuestas."""
    interval = 1.0 / stage.rps
    start = time.perf_counter_ns()
    inflight: set[asyncio.Task] = set()
    n = int(stage.rps * stage.seconds)

    async def one(intended_ns: int) -> None:
        payload = transaction(rng)
        sent = time.perf_counter_ns()
        try:
            r = await client.post(url, json=payload, timeout=timeout_s)
            stage.samples.append(Sample(intended_ns, sent, time.perf_counter_ns(), r.status_code))
        except Exception as exc:  # noqa: BLE001
            stage.samples.append(
                Sample(intended_ns, sent, time.perf_counter_ns(), 0, type(exc).__name__)
            )

    for i in range(n):
        intended = start + int(i * interval * 1e9)
        now = time.perf_counter_ns()
        if intended > now:
            await asyncio.sleep((intended - now) / 1e9)
        task = asyncio.create_task(one(intended))
        inflight.add(task)
        task.add_done_callback(inflight.discard)

    if inflight:
        await asyncio.gather(*list(inflight), return_exceptions=True)


def summarise(stage: Stage) -> dict:
    ok = [s for s in stage.samples if 200 <= s.status < 300]
    bad = [s for s in stage.samples if not (200 <= s.status < 300)]
    span_s = (max((s.done_ns for s in stage.samples), default=0)
              - min((s.intended_ns for s in stage.samples), default=0)) / 1e9
    errors: dict[str, int] = {}
    for s in bad:
        key = s.error or f"HTTP {s.status}"
        errors[key] = errors.get(key, 0) + 1
    return {
        "target_rps": stage.rps,
        "seconds": stage.seconds,
        "sent": len(stage.samples),
        "ok": len(ok),
        "errors": len(bad),
        "error_rate_pct": round(100 * len(bad) / max(1, len(stage.samples)), 3),
        "error_breakdown": errors,
        "achieved_rps": round(len(stage.samples) / span_s, 1) if span_s > 0 else 0.0,
        # El numero que se cita es el observado. El de servicio se publica al
        # lado para que se vea cuanto de la cola es del servidor y cuanto es
        # saturacion del emisor.
        "latency_observed_ms": percentiles([s.observed_ms for s in ok]),
        "latency_service_ms": percentiles([s.service_ms for s in ok]),
    }


def git_revision(repo: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "sin-git"
    except Exception:  # noqa: BLE001
        return "sin-git"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="endpoint que decide (scoring o ingesta)")
    ap.add_argument("--rps", type=int, default=500, help="tasa objetivo de una sola etapa")
    ap.add_argument("--seconds", type=int, default=120, help="duracion de la etapa")
    ap.add_argument("--ramp", help="escalera de tasas, p.ej. 100,500,1000,2000,5000")
    ap.add_argument("--step-seconds", type=int, default=60, help="duracion por peldano")
    ap.add_argument("--warmup-seconds", type=int, default=20,
                    help="calentamiento descartado: mata el arranque en frio")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=7, help="misma carga en cada corrida")
    ap.add_argument("--label", default="", help="etiqueta libre para el artefacto")
    ap.add_argument("--out", default="bench/resultados", help="carpeta de artefactos")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    stages = ([Stage(int(r), args.step_seconds) for r in args.ramp.split(",")]
              if args.ramp else [Stage(args.rps, args.seconds)])
    peak = max(s.rps for s in stages)

    limits = httpx.Limits(max_connections=peak * 2, max_keepalive_connections=peak)
    async with httpx.AsyncClient(limits=limits, http2=False) as client:
        if args.warmup_seconds:
            print(f"calentando {args.warmup_seconds}s a {min(50, stages[0].rps)} rps "
                  f"(se descarta)...", flush=True)
            await run_stage(client, args.url, Stage(min(50, stages[0].rps),
                                                    args.warmup_seconds), rng, args.timeout)

        results = []
        for stage in stages:
            print(f"midiendo {stage.rps} rps durante {stage.seconds}s...", flush=True)
            await run_stage(client, args.url, stage, rng, args.timeout)
            summary = summarise(stage)
            results.append(summary)
            obs = summary["latency_observed_ms"]
            print(f"  -> {summary['achieved_rps']} rps efectivos | "
                  f"p50 {obs.get('p50')} ms | p95 {obs.get('p95')} ms | "
                  f"p99 {obs.get('p99')} ms | errores {summary['error_rate_pct']}%",
                  flush=True)

    repo = Path(__file__).resolve().parent.parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = {
        "medido_en": datetime.now(timezone.utc).isoformat(),
        "revision": git_revision(repo),
        "url": args.url,
        "etiqueta": args.label,
        "config": {
            "semilla": args.seed, "timeout_s": args.timeout,
            "calentamiento_s": args.warmup_seconds,
            "lazo": "abierto",
            "latencia_reportada": "contra el instante previsto de envio "
                                  "(sin omision coordinada)",
        },
        "etapas": results,
    }
    out_dir = repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"loadtest-{args.label or 'run'}-{stamp}.json"
    (out_dir / name).write_text(json.dumps(artifact, indent=2, ensure_ascii=False),
                                encoding="utf-8")
    print(f"\nartefacto: {out_dir / name}")

    worst = max((r["latency_observed_ms"].get("p95", 0) for r in results), default=0)
    errs = max((r["error_rate_pct"] for r in results), default=0)
    print(f"peor p95 observado en la escalera: {worst} ms | peor tasa de error: {errs}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
