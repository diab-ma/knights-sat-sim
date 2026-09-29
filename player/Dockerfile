FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash coreutils xxd socat \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home player
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY python/ /usr/local/lib/python3.12/site-packages/
USER 1000:1000
ENV HOME=/home/player PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
CMD ["socat", "TCP-LISTEN:8766,bind=127.0.0.1,reuseaddr,fork", "UNIX-CONNECT:/bridge/raw.sock"]
