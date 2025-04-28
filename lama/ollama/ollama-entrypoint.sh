#!/bin/sh
set -e

ollama serve &

until curl -s http://localhost:11434 > /dev/null; do
  echo "Waiting for Ollama server to start..."
  sleep 1
done

# Pull the mistral model if not already present
MODEL="${MODEL_NAME}"

echo "==========================================="
echo "------------------- ${MODEL_NAME} ----------------"

ollama pull "${MODEL_NAME}"

sleep 10
ollama run "${MODEL_NAME}"

wait