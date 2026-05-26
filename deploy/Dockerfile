FROM python:3.12-slim

WORKDIR /app

# Copy application code (use deploy/backend for correct Docker import paths)
COPY deploy/backend/requirements.txt .
RUN pip config set global.timeout 300 && pip install --no-cache-dir -r requirements.txt

COPY deploy/backend/ backend/
COPY frontend/dist/ frontend/dist/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
