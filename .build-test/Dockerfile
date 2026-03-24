FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -s --connect-timeout 5 https://www.google.com | head -1 || echo "CURL_FAILED"
