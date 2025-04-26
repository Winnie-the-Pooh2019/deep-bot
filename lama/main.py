import logging
import os
from dotenv import load_dotenv
import requests
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

# ------------------------------------------------------------------------------
# Настройка логирования
# ------------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Константы и загрузка .env
# ------------------------------------------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL Ollama OpenAI-совместимого API
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/v1/chat/completions"
)

# (Опционально) API-ключ, если вы его настроили в Ollama
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

MODEL_NAME = os.getenv("MODEL_NAME")


# ------------------------------------------------------------------------------
# Функция запроса к Ollama
# ------------------------------------------------------------------------------
def get_model_response(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 10000,
        "stream": False
    }
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    try:
        response = requests.post(OLLAMA_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if "choices" in data and data["choices"]:
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        else:
            logger.warning("Неверный формат ответа от Ollama: %s", data)
            return "Ошибка: Неверный формат ответа от Ollama."
    except requests.exceptions.RequestException as e:
        logger.error("Ошибка при соединении с Ollama: %s", e)
        return f"Ошибка соединения с Ollama: {e}"


# ------------------------------------------------------------------------------
# Хендлеры Telegram
# ------------------------------------------------------------------------------
async def start(update: Update, context: CallbackContext) -> None:
    context.user_data["messages"] = []
    context.user_data["name"] = None
    await update.message.reply_text(
        "Здравствуйте! Вы обратились в приёмную комиссию КемГУ. Чем могу помочь?"
    )


async def respond_to_user(update: Update, context: CallbackContext) -> None:
    user_text = update.message.text
    user_id = update.effective_user.id

    context.user_data.setdefault("messages", [])
    context.user_data.setdefault("name", None)

    name = context.user_data["name"]
    logger.info("Пользователь %s задал вопрос: %s", user_id, user_text)

    if name is None:
        match = re.search(r"меня\s+зовут\s+([А-ЯЁа-яёA-Za-z]+)", user_text, re.IGNORECASE)
        if match:
            name = match.group(1)
            context.user_data["name"] = name
            logger.info("Пользователь %s представился именем: %s", user_id, name)

    system_message = {
        "role": "system",
        "content": (
            "Ты AI-помощник приёмной комиссии КемГУ. "
            "Отвечай коротко и по делу, обращайся по имени, "
            "если оно известно."
        )
    }

    history = [system_message] + context.user_data["messages"][-10:] + [
        {"role": "user", "content": user_text}
    ]

    content = get_model_response(history)

    context.user_data["messages"].append({"role": "user", "content": user_text})
    context.user_data["messages"].append({"role": "assistant", "content": content})

    if name:
        content = f"{name}, {content}"

    await update.message.reply_text(content)
    logger.info("Ответ бота пользователю %s: %s", user_id, content)


# ------------------------------------------------------------------------------
# Точка входа
# ------------------------------------------------------------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond_to_user))
    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
