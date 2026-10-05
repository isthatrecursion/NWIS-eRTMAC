FROM python:3.12-slim

WORKDIR /app
ENV NWIS_DATA_ROOT=/app/storage

# Install dependencies required for ML libraries (opencv, etc)
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/app ./app
COPY backend/migrations ./migrations

# Hugging Face Spaces require port 7860
EXPOSE 7860

# Run bootstrap and start FastAPI
CMD ["sh", "-c", "python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 7860"]
