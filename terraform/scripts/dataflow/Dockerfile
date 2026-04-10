FROM apache/beam_python3.12_sdk:2.56.0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY streaming_pipeline.py .

ENTRYPOINT ["python", "streaming_pipeline.py"]
