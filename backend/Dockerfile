FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY models/artifacts/ ./models/artifacts/
COPY backend/ ./backend/

WORKDIR /app/backend
ENV PYTHONPATH=/app:/app/backend

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
