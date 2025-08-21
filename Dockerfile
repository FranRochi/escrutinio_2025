FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema para mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential default-libmysqlclient-dev \
 && rm -rf /var/lib/apt/lists/*

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

EXPOSE 8000

# Entrypoint simple: espera DB y corre runserver
CMD ["sh","-c","./wait-for-it.sh db:3306 -- \
  python manage.py migrate && \
  python manage.py runserver 0.0.0.0:8000"]
