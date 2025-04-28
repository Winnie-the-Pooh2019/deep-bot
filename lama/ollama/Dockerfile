# Dockerfile
FROM ollama/ollama:latest

# install curl and nginx
RUN apt update \
 && apt install -y --no-install-recommends \
      curl \
 && rm -rf /var/lib/apt/lists/*

# copy entrypoint and nginx config
COPY ollama-entrypoint.sh /usr/local/bin/ollama-entrypoint.sh

# make entrypoint executable
RUN chmod +x /usr/local/bin/ollama-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/ollama-entrypoint.sh"]
