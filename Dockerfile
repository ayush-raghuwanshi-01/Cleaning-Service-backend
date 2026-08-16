FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY . .
RUN pip install --upgrade pip && pip install . && pip install "pytest>=8.3,<9" "pytest-asyncio>=0.24,<1" "httpx>=0.28,<1" "ruff>=0.8,<1"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
