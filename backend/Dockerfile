FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary avoids needing build-essential/libpq-dev, keeping the image small
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scraper ./scraper
COPY eval ./eval

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
