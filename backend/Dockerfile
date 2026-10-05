FROM python:3.12-slim

WORKDIR /app
ENV NWIS_DATA_ROOT=/app/storage
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
EXPOSE 8000
CMD ["sh", "-c", "python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
