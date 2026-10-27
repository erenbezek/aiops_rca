# quote-gateway imajı (DECISIONS 2026-10-28). Derleme: docker build -t aiops-quote-gateway:1 services/quote-gateway
# Taban sabit: python 3.12.14-slim (2026-09-19). Bağımlılıklar requirements.txt'te sabit. Kullanıcı root değil.
FROM python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
COPY gateway.py app.py ./
USER 10001
EXPOSE 8090
ENTRYPOINT ["opentelemetry-instrument", "python", "app.py"]
