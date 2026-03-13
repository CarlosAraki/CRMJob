FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema (se necessário)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Cria diretório para dados persistentes (volume)
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/crm_job.db

EXPOSE 9991

# Streamlit: porta 9991, binding em 0.0.0.0 para acesso externo
CMD ["streamlit", "run", "app.py", \
     "--server.port=9991", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
