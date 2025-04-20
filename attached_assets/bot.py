import os
import requests
import logging
import time
import datetime
import pytz
import random
from utils import format_error_for_display
from models import Post
from app import db

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
# Проверяем и корректируем формат CHANNEL_ID
_channel_id = os.environ.get('CHANNEL_ID', '@tradepotrest')
# Удаляем кириллические символы, которые могут вызывать проблемы
import re
_channel_id = re.sub(r'[^a-zA-Z0-9_@]', '', _channel_id)
# Добавляем @ если его нет в начале
if _channel_id and not _channel_id.startswith('@'):
    _channel_id = '@' + _channel_id
CHANNEL_ID = _channel_id
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEZONE = pytz.timezone('Asia/Dushanbe')

# История сообщений хранится в базе данных, это только для временного кеширования
post_history = []

# Trading topic suggestions
TRADING_TOPICS = [
    "🔥 Секреты успешного скальпинга на валютном рынке: мгновенные сделки и высокая прибыль",
    "📈 Свинг-трейдинг на фондовом рынке: как поймать долгосрочный тренд и заработать на волатильности",
    "💰 Пассивный доход: стратегии инвестирования в дивидендные акции с высокой доходностью",
    "🚀 Криптовалютная революция: как заработать на торговле Bitcoin и альткоинами в 2025 году",
    "📊 Мастерство технического анализа: как безошибочно читать графики и предсказывать движения рынка",
    "⚠️ Управление рисками: ключевой фактор долгосрочного успеха в трейдинге и инвестициях",
    "🧠 Психология победителя: как преодолеть страх и жадность для достижения стабильной прибыли",
    "🔍 Фундаментальный анализ: искусство выбора перспективных компаний и активов перед ростом",
    "⚡ Торговля фьючерсами: стратегии с высоким левериджем для опытных трейдеров",
    "🛡️ Опционные стратегии: как защитить свой портфель и получить дополнительный доход",
    "💎 Стратегии долгосрочного инвестирования в биткоин: от покупки до стейкинга и DeFi",
    "🔮 Топ-10 индикаторов технического анализа, которые должен знать каждый успешный трейдер",
    "🏢 Уровни поддержки и сопротивления: точки входа и выхода для максимальной прибыли",
    "🧩 Распознавание прибыльных паттернов графического анализа: от простого к сложному",
    "🛢️ Инвестиции в сырьевые товары: как диверсифицировать портфель и защитить капитал от инфляции",
    "💼 Построение сбалансированного инвестиционного портфеля: акции, облигации, ETF и альтернативные активы",
    "📱 Мобильный трейдинг: лучшие приложения и стратегии для торговли с телефона в любой точке мира",
    "😱 Самые опасные ошибки начинающих трейдеров и как их избежать: честный взгляд на риски",
    "🤖 Алгоритмическая торговля для новичков: первые шаги к автоматизации ваших стратегий",
    "💪 От новичка к профессионалу: история успеха трейдера, который превратил $1000 в миллион",
    "🌊 Торговля на волатильности: как извлечь прибыль в периоды паники и эйфории на рынке",
    "📰 Как правильно реагировать на экономические новости для принятия прибыльных торговых решений",
    "🔋 Энергетический сектор: перспективы инвестиций в традиционную и возобновляемую энергетику",
    "🏦 Банковский сектор: анализ акций финансовых компаний для долгосрочного роста капитала",
    "🧘‍♂️ Эмоциональный интеллект трейдера: как управлять стрессом и принимать рациональные решения"
]

def generate_post_text(prompt=None):
    """Generate text content using OpenRouter's GPT-4"""
    try:
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key is not set")
            # Создаем разнообразный резервный текст, зависящий от темы
            fallback_texts = [
                "🚀 Трейдинг - это искусство баланса и терпения! Каждая сделка учит нас чему-то новому. Помните: в долгосрочной перспективе выигрывают дисциплинированные. #трейдинг #инвестиции #tradepo",
                "💹 Финансовые рынки не прощают эмоциональных решений. Успешный трейдер - это хладнокровный стратег с четким планом действий! #биржа #аналитика #tradepo",
                "📊 Технический анализ - ваш лучший друг на рынке! Учитесь читать графики и видеть то, что другие упускают из виду. Преимущество в информации - ключ к успеху! #трейдинг #графики #tradepo",
                "💰 Инвестируйте в свои знания прежде, чем вкладывать деньги. Самое выгодное вложение - в собственное образование! #инвестиции #саморазвитие #tradepo",
                "⚡ Волатильность - не враг, а друг трейдера! Именно в периоды нестабильности рождаются самые прибыльные возможности. Будьте готовы! #трейдинг #прибыль #tradepo",
                "🔥 Дисциплина и строгое соблюдение риск-менеджмента - два столпа успешного трейдинга. Без них даже лучшая стратегия обречена на провал! #трейдинг #риски #tradepo"
            ]
            
            # Выбираем текст в зависимости от промпта
            if prompt:
                # Используем простую хеш-функцию для выбора текста на основе промпта
                index = sum(ord(c) for c in prompt) % len(fallback_texts)
                return fallback_texts[index]
            else:
                return random.choice(fallback_texts)
            
        headers = {
            "HTTP-Referer": "https://replit.com",  # Добавляем referer для OpenRouter
            "X-Title": "TRADEPO Bot",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Расширяем промпт, чтобы сделать его более содержательным
        user_prompt = prompt
        # Добавляем контекст к запросу для получения разнообразного контента
        current_time = datetime.datetime.now()
        content_request = f"Напиши авторитетный и подробный пост о трейдинге на тему: {user_prompt}"
        content_request += "\n\nДобавь неочевидные детали и полезные советы. Используй эмоциональный стиль с эмоджи."
        content_request += "\n\nВключи хэштеги #трейдинг #инвестиции #финансы #tradepo в конце поста."
        content_request += f"\n\nСоздай уникальный контент, не похожий на предыдущие посты. Текущая дата: {current_time.strftime('%d.%m.%Y')}."
            
        data = {
            "model": "anthropic/claude-3-haiku",  # Используем более доступную модель
            "messages": [
                {"role": "system", "content": "Ты - опытный финансовый аналитик и эксперт по трейдингу. Твой стиль письма - авторитетный, эмоциональный и полезный. Создавай уникальный контент."},
                {"role": "user", "content": content_request}
            ],
            "max_tokens": 250,  # Увеличиваем для более подробного контента
            "temperature": 0.9  # Увеличиваем для большего разнообразия
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating text, attempt {attempt+1}")
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions", 
                    headers=headers, 
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                
                # Более надежная обработка ответа
                response_data = response.json()
                logger.debug(f"API response: {response_data}")
                
                # Проверка формата ответа
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    if 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
                        text = response_data['choices'][0]['message']['content']
                    else:
                        # Запасной вариант, если структура ответа отличается
                        logger.warning("Unexpected response structure (no message/content)")
                        if 'text' in response_data:
                            text = response_data['text']
                        else:
                            raise KeyError("No recognizable text content in response")
                elif 'error' in response_data:
                    # Обработка ошибки API
                    error_message = response_data.get('error', {}).get('message', 'Unknown API error')
                    logger.error(f"API error: {error_message}")
                    raise KeyError(f"API error: {error_message}")
                else:
                    # Если не найдено поле choices, используем запасной вариант
                    logger.warning("No 'choices' field in response, trying fallback extraction")
                    # Попытка получить текст из произвольного поля
                    if 'output' in response_data:
                        text = response_data['output']
                    elif 'generated_text' in response_data:
                        text = response_data['generated_text']
                    else:
                        raise KeyError("Cannot extract text from response")
                logger.info(f"Text generated successfully: {text[:50]}...")
                return text
            except (requests.RequestException, KeyError) as e:
                error_msg = format_error_for_display(e)
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Text generation attempt {attempt+1} failed: {error_msg}. Retrying...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"All text generation attempts failed: {error_msg}")
                    raise
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Failed to generate text: {error_msg}")
        # Return fallback text
        return "Торговля на финансовых рынках - это искусство баланса между риском и доходностью. #tradepo"

def generate_image_description(text):
    """Generate an image description based on the post text"""
    try:
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key is not set")
            return "Trading chart with financial data on a dark blue background"
            
        headers = {
            "HTTP-Referer": "https://replit.com",  # Добавляем referer для OpenRouter
            "X-Title": "TRADEPO Bot",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Оптимизированный текст для экономии токенов
        input_text = text
        if input_text and len(input_text) > 40:
            # Если текст длинный, берем только начало
            input_text = input_text[:40] + "..."
            
        data = {
            "model": "anthropic/claude-3-haiku",  # Используем более доступную модель
            "messages": [
                {"role": "system", "content": "Опиши яркую, привлекательную картинку для поста о трейдинге. Добавь эмоциональные элементы и визуальные детали."},
                {"role": "user", "content": input_text}
            ],
            "max_tokens": 50  # Немного увеличиваем для более детальных описаний
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            headers=headers, 
            json=data,
            timeout=30
        )
        response.raise_for_status()
        
        # Более надежная обработка ответа
        response_data = response.json()
        logger.debug(f"API response for image description: {response_data}")
        
        # Проверка формата ответа
        if 'choices' in response_data and len(response_data['choices']) > 0:
            if 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
                description = response_data['choices'][0]['message']['content']
            else:
                # Запасной вариант, если структура ответа отличается
                logger.warning("Unexpected response structure for image description (no message/content)")
                if 'text' in response_data:
                    description = response_data['text']
                else:
                    raise KeyError("No recognizable text content in image description response")
        elif 'error' in response_data:
            # Обработка ошибки API
            error_message = response_data.get('error', {}).get('message', 'Unknown API error')
            logger.error(f"API error in image description: {error_message}")
            raise KeyError(f"API error: {error_message}")
        else:
            # Если не найдено поле choices, используем запасной вариант
            logger.warning("No 'choices' field in image description response, trying fallback extraction")
            # Попытка получить текст из произвольного поля
            if 'output' in response_data:
                description = response_data['output']
            elif 'generated_text' in response_data:
                description = response_data['generated_text']
            else:
                raise KeyError("Cannot extract text from image description response")
        logger.info(f"Image description generated: {description}")
        return description
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Failed to generate image description: {error_msg}")
        return "Professional trading chart with financial data visualization in dark theme"

def generate_image(text):
    """Generate image using Unsplash service"""
    try:
        # First generate a suitable description for the image based on the text
        image_description = generate_image_description(text)
        
        # Extract keywords from the description
        keywords = image_description.lower()
        
        # Replace common words with financial/trading terms to get better results
        if "chart" not in keywords:
            keywords += " chart"
        if "trading" not in keywords:
            keywords += " trading"
        
        # Clean up keywords - remove special characters, кириллицу и кавычки
        import re
        # Заменяем кириллические символы на латинские аналоги где возможно
        replacements = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
            'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'I', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'H', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA'
        }
        
        for cyr, lat in replacements.items():
            keywords = keywords.replace(cyr, lat)
            
        # Удаляем все нежелательные символы
        keywords = re.sub(r'[^a-zA-Z0-9\s]', ' ', keywords)
        keywords = " ".join(keywords.split()) # remove extra spaces
        
        # Select top keywords (max 4) to avoid too long URLs
        keywords_list = keywords.split()
        selected_keywords = []
        
        for keyword in keywords_list:
            if len(selected_keywords) < 4 and len(keyword) > 2:
                selected_keywords.append(keyword)
        
        if len(selected_keywords) == 0:
            # Use default keywords if none were extracted
            selected_keywords = ["trading", "finance", "chart"]
        
        search_term = "+".join(selected_keywords)
        
        # Try to get a relevant image from Unsplash
        try:
            # Use Unsplash source for simple image requests
            logger.info(f"Fetching image for keywords: {search_term}")
            
            # First try specific resolution
            unsplash_url = f"https://source.unsplash.com/1200x800/?{search_term}"
            
            # Make request to Unsplash
            response = requests.get(unsplash_url, allow_redirects=True, timeout=10)
            
            if response.status_code == 200:
                # Unsplash returned an image, return the final URL (after redirects)
                image_url = response.url
                logger.info(f"Image obtained successfully: {image_url}")
                return image_url
            else:
                logger.warning(f"Failed to get image from Unsplash: {response.status_code}")
                # Fallback to static image
                return get_fallback_image_url()
        except Exception as e:
            error_msg = format_error_for_display(e)
            logger.error(f"Error getting image from Unsplash: {error_msg}")
            return get_fallback_image_url()
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Failed to generate image: {error_msg}")
        return get_fallback_image_url()

# Отслеживание использованных изображений для избежания повторений
_last_images_used = []
_MAX_HISTORY = 5  # Количество последних использованных URL для отслеживания

def get_fallback_image_url(prompt=None):
    """Get a fallback image URL in case external services fail
    
    Args:
        prompt (str, optional): Текстовая тема поста, используется для детерминированного выбора
                               изображения, чтобы разные темы получали разные картинки
    
    Returns:
        str: URL изображения
    """
    global _last_images_used
    
    try:
        # Загружаем пользовательские URL изображений
        custom_images = []
        if os.path.exists('image_urls.txt'):
            with open('image_urls.txt', 'r', encoding='utf-8') as f:
                custom_images = [line.strip() for line in f.readlines() if line.strip()]
                
        # Запасной список, если пользовательских изображений нет
        fallback_images = [
            "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1611784728558-6a7645e72da1?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1640340434855-6084b1f4901c?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1642790551116-3ef6f3f2e184?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://i.imgur.com/zjjcJKZ.png",
            "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1569025690938-a00729c9e1f9?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80",
            "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80"
        ]
        
        # Объединяем пользовательские и встроенные изображения
        all_images = custom_images if custom_images else fallback_images
        available_count = len(all_images)
        
        if available_count == 0:
            logger.error("No images available")
            return "https://via.placeholder.com/1200x800?text=No+Images+Available"
        
        # Стратегия выбора изображения
        if prompt and len(all_images) > 1:
            # Детерминированный выбор на основе темы для связи темы с изображением
            # (одинаковые темы будут получать одинаковые изображения, разные - разные)
            # Используем простую хеш-функцию на основе темы
            hash_value = sum(ord(c) for c in prompt)
            index = hash_value % len(all_images)
            selected_image = all_images[index]
            
            # Если изображение недавно использовалось, выбираем другое
            attempts = 0
            while selected_image in _last_images_used and attempts < 3 and len(all_images) > len(_last_images_used):
                index = (index + 1) % len(all_images)
                selected_image = all_images[index]
                attempts += 1
                
            logger.info(f"Selected image based on prompt (index: {index} of {len(all_images)})")
        else:
            # Случайный выбор, исключая недавно использованные изображения
            available_images = [img for img in all_images if img not in _last_images_used]
            
            # Если все изображения уже были использованы недавно, сбрасываем историю
            if not available_images and len(all_images) > 1:
                available_images = all_images
                _last_images_used = []
                
            selected_image = random.choice(available_images)
            logger.info(f"Randomly selected image (available: {len(available_images)} of {len(all_images)})")
        
        # Обновляем историю использованных изображений
        _last_images_used.append(selected_image)
        if len(_last_images_used) > _MAX_HISTORY:
            _last_images_used.pop(0)  # Удаляем самое старое использованное изображение
            
        logger.info(f"Using image {'from custom list' if custom_images else 'from fallback list'} ({available_count} available)")
        return selected_image
        
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Error selecting image: {error_msg}")
        # В случае ошибки возвращаем стандартное изображение
        return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1200&h=800&q=80"

def send_to_telegram(image_url, caption):
    """Send post to Telegram channel"""
    if not TELEGRAM_TOKEN:
        logger.error("Telegram token is not set")
        return False, "Токен Telegram API не настроен"
        
    if not CHANNEL_ID:
        logger.error("Channel ID is not set")
        return False, "ID канала не настроен"
    
    try:
        # Сначала отправляем только текст - гарантированный способ
        telegram_text_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        text_payload = {
            'chat_id': CHANNEL_ID,
            'text': caption,
            'parse_mode': 'HTML'
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(telegram_text_url, data=text_payload, timeout=30)
                response.raise_for_status()
                # Get message_id for reference
                message_id = response.json().get('result', {}).get('message_id')
                logger.info(f"Text message sent to Telegram with ID: {message_id}")
                
                # Затем пробуем отправить фото отдельно, если удалось отправить текст
                if image_url and image_url.startswith(('http://', 'https://')):
                    try:
                        media_payload = {
                            'chat_id': CHANNEL_ID,
                            'photo': image_url
                        }
                        media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                        media_response = requests.post(media_url, data=media_payload, timeout=30)
                        
                        if media_response.status_code == 200:
                            logger.info("Image sent to Telegram successfully")
                        else:
                            logger.warning(f"Failed to send image, but text was sent. Status: {media_response.status_code}")
                    except Exception as img_e:
                        logger.warning(f"Failed to send image, but text was sent. Error: {img_e}")
                
                return True, message_id
            except requests.RequestException as e:
                error_msg = format_error_for_display(e)
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Telegram send attempt {attempt+1} failed: {error_msg}. Retrying...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"All Telegram send attempts failed: {error_msg}")
                    raise
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Failed to send to Telegram: {error_msg}")
        return False, error_msg

def create_and_send_post(theme=None):
    """Create and send a post to the Telegram channel"""
    start_time = time.time()
    
    try:
        logger.info(f"Creating post with theme: {theme}")
        
        # Record for database
        post_record = Post(
            theme=theme,
            timestamp=datetime.datetime.now(TIMEZONE)
        )
        
        # Generate text content based on theme
        text = generate_post_text(theme)
        logger.info(f"Generated text: {text[:100]}...")
        
        # Update post record with text snippet (first 200 chars)
        post_record.text_snippet = text[:200] + ('...' if len(text) > 200 else '')
        post_record.full_text = text
        
        # Generate image URL
        image_url = generate_image(text)
        logger.info(f"Generated image URL: {image_url}")
        post_record.image_url = image_url
        
        # Send to Telegram
        success, result = send_to_telegram(image_url, text)
        
        # Update post record
        post_record.success = success
        post_record.message_id = result if success else None
        post_record.error = None if success else result
        
        # Calculate processing time
        elapsed_time = time.time() - start_time
        processing_time = f"{elapsed_time:.2f}s"
        post_record.processing_time = processing_time
        
        # Save to database
        try:
            from app import db
            with db.session.begin():
                db.session.add(post_record)
                logger.info(f"Post saved to database with ID: {post_record.id}")
        except Exception as db_error:
            logger.error(f"Error saving post to database: {db_error}")
            # Still continue to return the result even if DB save failed
            # Also add to in-memory history as fallback
            post_history.append(post_record)
            
        logger.info(f"Post created and sent: success={success}, processing_time={processing_time}")
        
        return success, text, image_url, result
    except Exception as e:
        error_msg = format_error_for_display(e)
        logger.error(f"Error creating and sending post: {error_msg}")
        
        # Create failed post record for tracking
        try:
            failed_post = Post(
                theme=theme,
                timestamp=datetime.datetime.now(TIMEZONE),
                text_snippet="Ошибка генерации",
                full_text=f"Произошла ошибка: {error_msg}",
                success=False,
                error=error_msg,
                processing_time=f"{time.time() - start_time:.2f}s"
            )
            
            # Try to save to database
            try:
                from app import db
                with db.session.begin():
                    db.session.add(failed_post)
            except Exception as db_error:
                logger.error(f"Error saving failed post to database: {db_error}")
                # Add to in-memory history as fallback
                post_history.append(failed_post)
        except Exception as record_error:
            logger.error(f"Error creating failure record: {record_error}")
        
        return False, "Ошибка при создании поста", None, error_msg

_used_topics = []
_max_topic_history = 10

def get_random_topic():
    """Get a random topic for post generation that wasn't used recently"""
    global _used_topics
    
    available_topics = [t for t in TRADING_TOPICS if t not in _used_topics]
    if not available_topics:
        # If all topics were used, reset history
        _used_topics = []
        available_topics = TRADING_TOPICS
        
    topic = random.choice(available_topics)
    _used_topics.append(topic)
    
    # Keep only recent history
    if len(_used_topics) > _max_topic_history:
        _used_topics.pop(0)
        
    return topic

def get_post_history():
    """Return the post history from database
    Returns the most recent posts from the database, or in-memory history as fallback
    """
    try:
        # Query posts from the database
        from app import db
        posts = db.session.query(Post).order_by(Post.timestamp.desc()).limit(20).all()
        
        # Convert to dictionary for easier handling in templates
        post_dicts = [post.to_dict() for post in posts]
        
        logger.info(f"Retrieved {len(post_dicts)} posts from database")
        return post_dicts
    except Exception as e:
        logger.error(f"Error getting post history from database: {e}")
        # Fallback to in-memory history
        logger.info(f"Using in-memory post history as fallback ({len(post_history)} posts)")
        return [post.to_dict() if hasattr(post, 'to_dict') else post for post in post_history]