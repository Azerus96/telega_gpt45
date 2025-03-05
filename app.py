import os
import gradio as gr
import requests
import json
import time
import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("telegram-bot-interface")

# Доступные модели в боте
TELEGRAM_MODELS = [
    "GPT-4o",
    "GPT-4 Turbo",
    "Claude 3 Opus",
    "Claude 3 Sonnet",
    "Claude 3 Haiku",
    "Gemini Pro",
    "DALL-E 3"
]

# Функция для отправки сообщения боту через прокси-сервер
def send_message_to_bot(message, model_name, history=None):
    try:
        # URL вашего прокси-сервера (будет работать в том же приложении)
        proxy_url = "http://localhost:8000/send_message"
        
        # Подготовка данных для запроса
        data = {
            "message": message,
            "model": model_name,
            "history": history if history else []
        }
        
        # Отправка запроса к прокси-серверу
        response = requests.post(
            proxy_url,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json().get("response", "Нет ответа от бота")
        else:
            return f"Ошибка при обращении к боту: {response.status_code}"
    except Exception as e:
        logger.exception(f"Ошибка при отправке сообщения боту: {str(e)}")
        return f"Ошибка: {str(e)}"

# Создание интерфейса
with gr.Blocks(theme=gr.themes.Soft(), css="""
    footer {visibility: hidden}
    .generating {
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% {opacity: 1;}
        50% {opacity: 0.5;}
        100% {opacity: 1;}
    }
""") as demo:
    gr.Markdown("# AI Ассистент | GPT, DALL-E, Claude | OpenAI")
    
    with gr.Row():
        with gr.Column(scale=3):
            model_dropdown = gr.Dropdown(
                choices=TELEGRAM_MODELS,
                label="Модель",
                value=TELEGRAM_MODELS[0],
                info="Доступные модели в Telegram-боте"
            )
    
    with gr.Accordion("Настройки", open=False):
        system_message = gr.Textbox(
            label="Системное сообщение",
            placeholder="Введите системное сообщение для модели...",
            lines=2
        )
        
        with gr.Row():
            temperature_slider = gr.Slider(
                minimum=0.0, 
                maximum=2.0, 
                value=0.7, 
                step=0.1, 
                label="Температура",
                info="Контролирует случайность ответов (может не поддерживаться ботом)"
            )
    
    chatbot = gr.Chatbot(height=500, show_copy_button=True)
    
    with gr.Row():
        with gr.Column(scale=8):
            msg = gr.Textbox(
                show_label=False,
                placeholder="Введите сообщение...",
                container=False,
                lines=3
            )
        with gr.Column(scale=1, min_width=50):
            submit_btn = gr.Button("Отправить", variant="primary")
    
    file_upload = gr.File(label="Прикрепить файл (может не поддерживаться)")
    
    with gr.Row():
        clear = gr.Button("Очистить чат")
    
    # Индикатор состояния
    status_indicator = gr.Markdown("Готов к работе")
    
    # Функция для обработки сообщений
    def user_input(message, chat_history, file, model_name, temperature, system_msg):
        logger.info(f"Получено сообщение: {message[:50]}...")
        
        # Проверка на None
        if chat_history is None:
            chat_history = []
            
        if not message:
            return "", chat_history, None, "Введите сообщение"
        
        # Обновляем статус
        yield "", chat_history, None, "Обработка сообщения..."
        
        # Добавляем сообщение пользователя в историю
        chat_history.append((message, None))
        yield "", chat_history, None, "Отправка сообщения боту..."
        
        # Подготовка истории для отправки боту
        history_for_bot = []
        for user_msg, bot_msg in chat_history[:-1]:
            history_for_bot.append({"role": "user", "content": user_msg})
            if bot_msg:
                history_for_bot.append({"role": "assistant", "content": bot_msg})
        
        # Если есть системное сообщение, добавляем его
        if system_msg:
            history_for_bot.insert(0, {"role": "system", "content": system_msg})
        
        # Получаем ответ от бота
        try:
            bot_message = send_message_to_bot(message, model_name, history_for_bot)
            chat_history[-1] = (message, bot_message)
            yield "", chat_history, None, "Готов к работе"
        except Exception as e:
            logger.exception(f"Ошибка при получении ответа от бота: {str(e)}")
            bot_message = f"Ошибка: {str(e)}"
            chat_history[-1] = (message, bot_message)
            yield "", chat_history, None, "Произошла ошибка"
        
        return "", chat_history, None, "Готов к работе"
    
    # Функция для очистки чата
    def clear_chat():
        logger.info("Очистка чата")
        return [], None, "Чат очищен"
    
    # Привязка событий
    msg.submit(user_input, [msg, chatbot, file_upload, model_dropdown, temperature_slider, system_message], 
               [msg, chatbot, file_upload, status_indicator])
    
    submit_btn.click(user_input, [msg, chatbot, file_upload, model_dropdown, temperature_slider, system_message], 
                    [msg, chatbot, file_upload, status_indicator])
    
    clear.click(clear_chat, outputs=[chatbot, file_upload, status_indicator])

# Запуск приложения
if __name__ == "__main__":
    logger.info("Запуск приложения...")
    port = int(os.environ.get("PORT", 7860))
    logger.info(f"Используется порт: {port}")
    
    # Запускаем прокси-сервер в отдельном потоке
    import threading
    from telegram_proxy import start_proxy_server
    
    proxy_thread = threading.Thread(target=start_proxy_server)
    proxy_thread.daemon = True
    proxy_thread.start()
    
    demo.launch(server_name="0.0.0.0", server_port=port)
