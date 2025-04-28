import logging
import os
from dotenv import load_dotenv
import re

from ollama import Client
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
# Загрузка переменных окружения
# ------------------------------------------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL_NAME     = os.getenv("MODEL_NAME")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")

try:
    client = Client(host=OLLAMA_API_URL)
except Exception as e:
    logger.error("Ошибка при подключении к Ollama: %s", e)
    exit(-1)


# ------------------------------------------------------------------------------
# Функция запроса к Ollama через библиотеку
# ------------------------------------------------------------------------------
def get_model_response(messages):
    """
    Вызывает ollama.chat вместо запроса через requests.
    Возвращает сгенерированный текст или сообщение об ошибке.
    """
    try:
        # Вызываем chat API
        response = client.chat(
            model=MODEL_NAME,
            messages=messages,
            stream=False
        )
        # Извлекаем содержимое
        # Библиотека позволяет обращаться как к dict, так и к атрибутам
        content = response["message"]["content"].strip()
        # Убираем теги <think>...</think>, если они есть
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    except Exception as e:
        logger.error("Ошибка при вызове Ollama: %s", e)
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

    # Определяем имя пользователя по фразе "меня зовут ..."
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

    # Обновляем историю
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
