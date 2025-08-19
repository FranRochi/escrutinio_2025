FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema para mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential default-libmysqlclient-dev \
 && rm -rf /var/lib/apt/lists/*

# Requisitos primero (mejor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copiar código (incluye wait-for-it.sh)
COPY . .

# Permisos
RUN chmod +x wait-for-it.sh

EXPOSE 8000

# Entrypoint: espera DB, migra, static, gunicorn
CMD ["sh","-c","./wait-for-it.sh db:3306 -- \
  python manage.py migrate && \
  python manage.py collectstatic --noinput && \
  gunicorn backend.wsgi:application -b 0.0.0.0:8000 --workers 3 --timeout 60"]
