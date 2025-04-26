FROM python:3.12-alpine

# Работаем в /app
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
COPY .env .
COPY main.py .

RUN python3 -m venv /app/.venv
RUN source /app/.venv/bin/activate
RUN pip install --no-cache-dir -r requirements.txt

# Запуск бота
ENTRYPOINT ["python", "main.py"]
