FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD python -c "from ml_backend import create_app; from ml_backend.extensions import db; app = create_app(); app.app_context().push(); db.create_all()" && gunicorn --bind 0.0.0.0:${PORT:-8000} "ml_backend:create_app()"
