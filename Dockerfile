FROM python:3.12.16-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .

ENV INVENTORY_DB=/data/inventory.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN mkdir -p /data

CMD ["python", "main.py"]
