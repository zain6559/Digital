FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends android-tools-adb curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium
COPY app ./app
CMD ["sh","-c","uvicorn app.main:app --host ${NOOR_BACKEND_HOST:-0.0.0.0} --port ${NOOR_BACKEND_PORT:-8000}"]
