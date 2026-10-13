# Stage 1: Build Angular Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Python + MS SQL ODBC Driver 18 + App
FROM python:3.12-slim

# Previne prompts interativos e define encoding
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENSSL_CONF=/etc/ssl/openssl_custom.cnf \
    PORT=8080

WORKDIR /app

# Instala dependências de sistema e o Microsoft ODBC Driver 17 e 18 for SQL Server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    build-essential \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY openssl.cnf /etc/ssl/openssl_custom.cnf

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte do backend
COPY src/ ./src/
COPY main.py .

# Copia os arquivos compilados do frontend para o diretório esperado pelo FastAPI
COPY --from=frontend-builder /app/frontend/dist/frontend/browser ./frontend/dist/frontend/browser

# Expõe a porta do Cloud Run
EXPOSE 8080

# Inicia o servidor Uvicorn escutando na porta definida pela variável PORT
CMD ["sh", "-c", "uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
