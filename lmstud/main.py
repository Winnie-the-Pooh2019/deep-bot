import logging
import os
from dotenv import load_dotenv
import requests
import re
from telegram import Update
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext)

# ------------------------------------------------------------------------------
# Настройка логирования
# ------------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ------------------------------------------------------------------------------
# Константы
# ------------------------------------------------------------------------------
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
LM_STUDIO_URL = os.getenv("LM_STUDIO_LINK")
MODEL_NAME = os.getenv("MODEL_NAME")


# ------------------------------------------------------------------------------
# Функции
# ------------------------------------------------------------------------------
def get_model_response(messages):
    """
    Делает POST-запрос к LM Studio, передавая список сообщений (history).
    Возвращает текст, сгенерированный моделью, или сообщение об ошибке.
    """
    # Формируем JSON-параметры для запроса
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.9,  # степень "креативности" модели
        "max_tokens": 10000,  # максимальное число генерируемых токенов
        "stream": False  # отключаем стриминг для простоты
    }

    # Заголовки для POST-запроса
    headers = {"Content-Type": "application/json"}

    try:
        # Отправляем запрос
        response = requests.post(LM_STUDIO_URL, headers=headers, json=payload)
        # Если код ответа не 2xx, выбрасываем исключение
        response.raise_for_status()
        # Парсим JSON
        response_json = response.json()

        # Проверяем структуру ответа (поле "choices" и его содержимое)
        if "choices" in response_json and len(response_json["choices"]) > 0:
            content = response_json["choices"][0]["message"]["content"].strip()

            # Удаляем теги <think>...</think>, если модель их генерирует
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            return content
        else:
            # Если вдруг структура ответа не такая, как ожидаем
            logger.warning("Неверный формат ответа от LM Studio. Ответ: %s", response_json)
            return "Ошибка: Неверный формат ответа от LM Studio."
    except requests.exceptions.RequestException as e:
        # Логируем и возвращаем сообщение об ошибке соединения
        logger.error("Ошибка при соединении с LM Studio: %s", e)
        return f"Ошибка соединения с LM Studio: {e}"


async def start(update: Update, context: CallbackContext) -> None:
    """
    Команда /start. Сбрасывает историю общения и приветствует пользователя.
    """
    # Очищаем данные пользователя
    context.user_data["messages"] = []
    context.user_data["name"] = None

    await update.message.reply_text(
        "Здравствуйте! Вы обратились в приёмную комиссию Кемеровского государственного университета. Чем могу помочь?"
    )


async def respond_to_user(update: Update, context: CallbackContext) -> None:
    """
    Обработчик обычных текстовых сообщений.
    Запоминает историю, проверяет, не представился ли пользователь,
    формирует запрос к LM Studio и возвращает ответ.
    """
    # Текст сообщения от пользователя
    user_text = update.message.text

    # Получаем user_id (если вдруг будет нужно для логики)
    user_id = update.effective_user.id

    # Инициализация структуры user_data, если не инициализировано
    if "messages" not in context.user_data:
        context.user_data["messages"] = []
    if "name" not in context.user_data:
        context.user_data["name"] = None

    # Текущее имя пользователя (если он уже представился)
    name = context.user_data["name"]

    # Логируем входящее сообщение
    logger.info("Пользователь %s задал вопрос: %s", user_id, user_text)

    # Проверяем, представился ли пользователь (ключевые слова "меня зовут ...")
    # Можно расширить, если нужно более сложное определение имени
    if name is None:
        match = re.search(r"меня\s+зовут\s+([А-ЯЁа-яёA-Za-z]+)", user_text, re.IGNORECASE)
        if match:
            # Сохраняем имя в user_data
            name = match.group(1)
            context.user_data["name"] = name
            logger.info("Пользователь %s представился именем: %s", user_id, name)

    # Формируем "system" сообщение — это контекст, который задаёт роль ассистента
    system_message = {
        "role": "system",
        "content": (
            "Ты AI-помощник приёмной комиссии Кемеровского государственного университета. "
            "Отвечай на вопросы абитуриентов о поступлении, документах, сроках и экзаменах.\n\n"
            "## ВАЖНО:\n"
            "- Если знаешь имя пользователя, обращайся к нему по имени.\n"
            "- Не повторяй одно и то же приветствие в каждом сообщении.\n"
            "- Говори кратко и по делу.\n"
            "- Если не знаешь ответ, предложи обратиться в приёмную комиссию или на сайт университета."
        )
    }

    # Собираем историю (оставляем только последние 10 сообщений, если история большая)
    # 1. system_message (общий контекст)
    # 2. последние 10 записей из истории
    # 3. новое сообщение пользователя
    history = [system_message] + context.user_data["messages"][-10:] + [
        {"role": "user", "content": user_text}
    ]

    # Отправляем историю в LM Studio и получаем ответ
    content = get_model_response(history)

    # Сохраняем в историю текущее "user" сообщение
    context.user_data["messages"].append({"role": "user", "content": user_text})
    # Сохраняем ответ модели
    context.user_data["messages"].append({"role": "assistant", "content": content})

    # Если знаем имя пользователя, добавим его в начало ответа
    if name:
        content = f"{name}, {content}"

    # Если не хотите разбивать, просто отправляем, но будьте готовы к ограничению
    await update.message.reply_text(content)

    # Логируем ответ
    logger.info("Ответ бота пользователю %s: %s", user_id, content)


def main():
    """
    Основная функция, инициализирует приложение, регистрирует обработчики
    и запускает polling.
    """
    # Создаём приложение Telegram
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Обработчик команды /start
    app.add_handler(CommandHandler("start", start))
    # Обработчик любых текстовых сообщений (кроме команд)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond_to_user))

    logger.info("Бот запущен и ожидает сообщения...")
    # Запуск бота в режиме polling (опрос сервера Telegram)
    app.run_polling()


# ------------------------------------------------------------------------------
# Точка входа
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
