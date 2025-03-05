from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerUser

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("telegram-proxy")

# Данные для авторизации в Telegram
API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE_NUMBER")
BOT_USERNAME = "gpt_rubq_bot"

# Создание клиента Telegram
client = TelegramClient('telegram_session', API_ID, API_HASH)

# Словарь для хранения ожидающих ответов
waiting_responses = {}

# Модель данных для запроса
class MessageRequest(BaseModel):
    message: str
    model: str
    history: Optional[List[Dict[str, Any]]] = None

# Модель данных для ответа
class MessageResponse(BaseModel):
    response: str

# Создание FastAPI приложения
app = FastAPI()

# Обработчик событий для получения сообщений от бота
@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def handle_bot_response(event):
    message_id = event.message.id
    message_text = event.message.text
    
    # Проверяем, есть ли ожидающие ответа запросы
    for request_id, data in list(waiting_responses.items()):
        if not data.get("response_received"):
            # Помечаем, что ответ получен
            waiting_responses[request_id]["response"] = message_text
            waiting_responses[request_id]["response_received"] = True
            logger.info(f"Получен ответ от бота для запроса {request_id}")
            break

# Эндпоинт для отправки сообщений боту
@app.post("/send_message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        logger.error("Клиент не авторизован в Telegram")
        raise HTTPException(status_code=401, detail="Не авторизован в Telegram")
    
    try:
        # Получаем информацию о боте
        bot_entity = await client.get_entity(BOT_USERNAME)
        
        # Создаем уникальный ID для запроса
        request_id = f"{request.model}_{len(request.message)}"
        waiting_responses[request_id] = {"response_received": False}
        
        # Если указана модель, отправляем команду для выбора модели
        if request.model:
            model_command = f"/model {request.model}"
            await client.send_message(bot_entity, model_command)
            # Ждем немного, чтобы бот обработал команду
            await asyncio.sleep(1)
        
        # Отправляем сообщение боту
        await client.send_message(bot_entity, request.message)
        logger.info(f"Сообщение отправлено боту: {request.message[:50]}...")
        
        # Ждем ответа от бота (максимум 60 секунд)
        for _ in range(60):
            if waiting_responses[request_id].get("response_received"):
                response_text = waiting_responses[request_id]["response"]
                del waiting_responses[request_id]
                return {"response": response_text}
            await asyncio.sleep(1)
        
        # Если ответ не получен за 60 секунд
        del waiting_responses[request_id]
        return {"response": "Бот не ответил в течение 60 секунд. Попробуйте еще раз."}
    
    except Exception as e:
        logger.exception(f"Ошибка при отправке сообщения боту: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

# Функция для запуска прокси-сервера
def start_proxy_server():
    # Запускаем клиент Telegram
    client.start(phone=PHONE_NUMBER)
    
    # Запускаем FastAPI сервер
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    start_proxy_server()
