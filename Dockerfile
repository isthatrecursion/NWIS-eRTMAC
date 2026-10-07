FROM python:3.12-slim

WORKDIR /app
ENV NWIS_DATA_ROOT=/app/storage

# Install dependencies required for ML libraries (opencv, etc)
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app
COPY backend/migrations ./migrations

# Hugging Face Spaces use 7860; Railway provides PORT at runtime.
EXPOSE 7860

# Bootstrap the synthetic demo before accepting requests.
CMD ["sh", "-c", "python -m app.bootstrap && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
