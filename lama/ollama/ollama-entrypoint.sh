#!/bin/sh
set -e

ollama serve &

until curl -s http://localhost:11434 > /dev/null; do
  echo "Waiting for Ollama server to start..."
  sleep 1
done

# Pull the mistral model if not already present
MODEL="${MODEL_NAME}"

if ! ollama list | grep -q "$MODEL"; then
  echo "Pulling mistral model..."
  ollama pull "$MODEL"

else
  echo "model already present."
fi

sleep 10
ollama run "$MODEL"

wait