import os
import requests
import logging
import time
import datetime
import pytz
import random
import json
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
# Check and correct CHANNEL_ID format
_channel_id = os.environ.get('CHANNEL_ID', '@tradepotrest')
# Remove Cyrillic characters that may cause problems
import re
_channel_id = re.sub(r'[^a-zA-Z0-9_@]', '', _channel_id)
# Add @ if it's not at the beginning
if _channel_id and not _channel_id.startswith('@'):
    _channel_id = '@' + _channel_id
CHANNEL_ID = _channel_id
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEZONE = pytz.timezone('Asia/Dushanbe')

# Post history is stored in database, this is only for temporary caching
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
    """Generate text content using OpenRouter's GPT-4 or Claude"""
    try:
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key is not set")
            # Create diverse fallback text based on the topic
            fallback_texts = [
                "🚀 Трейдинг - это искусство баланса и терпения! Каждая сделка учит нас чему-то новому. Помните: в долгосрочной перспективе выигрывают дисциплинированные. #трейдинг #инвестиции #tradepo",
                "💹 Финансовые рынки не прощают эмоциональных решений. Успешный трейдер - это хладнокровный стратег с четким планом действий! #биржа #аналитика #tradepo",
                "📊 Технический анализ - ваш лучший друг на рынке! Учитесь читать графики и видеть то, что другие упускают из виду. Преимущество в информации - ключ к успеху! #трейдинг #графики #tradepo",
                "💰 Инвестируйте в свои знания прежде, чем вкладывать деньги. Самое выгодное вложение - в собственное образование! #инвестиции #саморазвитие #tradepo",
                "⚡ Волатильность - не враг, а друг трейдера! Именно в периоды нестабильности рождаются самые прибыльные возможности. Будьте готовы! #трейдинг #прибыль #tradepo",
                "🔥 Дисциплина и строгое соблюдение риск-менеджмента - два столпа успешного трейдинга. Без них даже лучшая стратегия обречена на провал! #трейдинг #риски #tradepo"
            ]
            
            # Choose text based on prompt
            if prompt:
                # Use simple hash function to select text based on prompt
                index = sum(ord(c) for c in prompt) % len(fallback_texts)
                return fallback_texts[index]
            else:
                return random.choice(fallback_texts)
            
        headers = {
            "HTTP-Referer": "https://replit.com",  # Add referer for OpenRouter
            "X-Title": "TRADEPO Bot",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Expand prompt to make it more substantial
        user_prompt = prompt
        # Add context to request for diverse content
        current_time = datetime.datetime.now()
        content_request = f"Напиши авторитетный и подробный пост о трейдинге на тему: {user_prompt}"
        content_request += "\n\nДобавь неочевидные детали и полезные советы. Используй эмоциональный стиль с эмоджи."
        content_request += "\n\nВключи хэштеги #трейдинг #инвестиции #финансы #tradepo в конце поста."
        content_request += f"\n\nСоздай уникальный контент, не похожий на предыдущие посты. Текущая дата: {current_time.strftime('%d.%m.%Y')}."
            
        data = {
            "model": "anthropic/claude-3-haiku",  # Use more accessible model
            "messages": [
                {"role": "system", "content": "Ты - опытный финансовый аналитик и эксперт по трейдингу. Твой стиль письма - авторитетный, эмоциональный и полезный. Создавай уникальный контент."},
                {"role": "user", "content": content_request}
            ],
            "max_tokens": 250,  # Increase for more detailed content
            "temperature": 0.9  # Increase for more variety
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
                
                # More robust response handling
                response_data = response.json()
                logger.debug(f"API response: {response_data}")
                
                # Check response format
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    if 'message' in response_data['choices'][0] and 'content' in response_data['choices'][0]['message']:
                        text = response_data['choices'][0]['message']['content']
                    else:
                        # Fallback if structure is different
                        logger.warning("Unexpected response structure (no message/content)")
                        if 'text' in response_data:
                            text = response_data['text']
                        else:
                            raise KeyError("No recognizable text content in response")
                elif 'error' in response_data:
                    # Handle API error
                    error_message = response_data.get('error', {}).get('message', 'Unknown API error')
                    logger.error(f"API error: {error_message}")
                    raise KeyError(f"API error: {error_message}")
                else:
                    # If no choices field, use fallback
                    logger.warning("No 'choices' field in response, trying fallback extraction")
                    # Try to get text from arbitrary field
                    if 'output' in response_data:
                        text = response_data['output']
                    elif 'generated_text' in response_data:
                        text = response_data['generated_text']
                    else:
                        raise KeyError("Could not extract text from response")
                
                # Remove any markdown syntax that might be present
                text = text.replace('```', '').strip()
                
                logger.info(f"Generated text: {text[:50]}...")
                return text
                
            except Exception as e:
                logger.error(f"Error in text generation attempt {attempt+1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    # If all retries failed, return error
                    raise Exception(f"Failed to generate text after {MAX_RETRIES} attempts: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error in generate_post_text: {e}")
        # Return simple fallback text
        return f"📊 Важное напоминание для всех трейдеров: анализируйте рынок перед каждой сделкой и следуйте своему торговому плану. Успешный трейдинг строится на дисциплине! #{prompt.replace(' ', '')} #трейдинг #tradepo"

def get_image_url():
    """Get a random image URL from the image_urls.txt file"""
    try:
        if os.path.exists('image_urls.txt'):
            with open('image_urls.txt', 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
                
            if urls:
                return random.choice(urls)
                
    except Exception as e:
        logger.error(f"Error getting image URL: {e}")
        
    # Default image if none available
    return None

def send_telegram_message(text, image_url=None):
    """Send message to Telegram channel"""
    if not TELEGRAM_TOKEN:
        logger.error("Telegram token is not set")
        return False, "Telegram token is not set"
        
    if not CHANNEL_ID:
        logger.error("Channel ID is not set")
        return False, "Channel ID is not set"
        
    try:
        api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        
        if image_url:
            # Send photo with caption
            endpoint = api_url + "sendPhoto"
            data = {
                "chat_id": CHANNEL_ID,
                "photo": image_url,
                "caption": text,
                "parse_mode": "HTML"
            }
        else:
            # Send text message
            endpoint = api_url + "sendMessage"
            data = {
                "chat_id": CHANNEL_ID,
                "text": text,
                "parse_mode": "HTML"
            }
            
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Sending message to Telegram, attempt {attempt+1}")
                response = requests.post(endpoint, data=data, timeout=30)
                response.raise_for_status()
                
                response_data = response.json()
                logger.debug(f"Telegram API response: {response_data}")
                
                if response_data.get('ok', False):
                    message_id = response_data.get('result', {}).get('message_id', None)
                    logger.info(f"Message sent successfully, message_id: {message_id}")
                    return True, message_id
                else:
                    error_description = response_data.get('description', 'Unknown error')
                    logger.error(f"Telegram API error: {error_description}")
                    return False, error_description
                    
            except Exception as e:
                logger.error(f"Error in send attempt {attempt+1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    # If all retries failed
                    return False, f"Failed to send message after {MAX_RETRIES} attempts: {str(e)}"
                    
    except Exception as e:
        logger.error(f"Error in send_telegram_message: {e}")
        return False, str(e)

def create_and_send_post(theme):
    """Create and send a post to the Telegram channel"""
    start_time = time.time()
    success = False
    text = None
    image_url = None
    result = None
    error = None
    
    try:
        logger.info(f"Creating post with theme: {theme}")
        
        # Generate text for the post
        text = generate_post_text(theme)
        
        # Get random image URL
        image_url = get_image_url()
        
        # Send message to Telegram
        success, result = send_telegram_message(text, image_url)
        
        # Calculate processing time
        processing_time = f"{time.time() - start_time:.2f}s"
        
        # Save post to database
        try:
            # Create a snippet for display
            text_snippet = text[:200] + "..." if text and len(text) > 200 else text
            
            # Create new post record
            post = Post(
                theme=theme,
                text_snippet=text_snippet,
                full_text=text,
                image_url=image_url,
                success=success,
                message_id=result if success else None,
                error=result if not success else None,
                processing_time=processing_time
            )
            
            # Add to database
            db.session.add(post)
            db.session.commit()
            
            # Add to in-memory cache
            post_dict = post.to_dict()
            post_history.insert(0, post_dict)
            
            # Keep only last 100 posts in memory
            if len(post_history) > 100:
                post_history.pop()
                
            logger.info(f"Post saved to database with ID: {post.id}")
            
        except Exception as db_error:
            logger.error(f"Error saving post to database: {db_error}")
            error = f"Database error: {str(db_error)}"
            
        return success, text, image_url, result
        
    except Exception as e:
        logger.error(f"Error in create_and_send_post: {e}")
        error_message = format_error_for_display(e)
        
        # Try to save error to database
        try:
            processing_time = f"{time.time() - start_time:.2f}s"
            
            post = Post(
                theme=theme,
                text_snippet=text[:200] + "..." if text and len(text) > 200 else text,
                full_text=text,
                image_url=image_url,
                success=False,
                error=error_message,
                processing_time=processing_time
            )
            
            db.session.add(post)
            db.session.commit()
            
            post_dict = post.to_dict()
            post_history.insert(0, post_dict)
            
            if len(post_history) > 100:
                post_history.pop()
                
        except Exception as db_error:
            logger.error(f"Error saving error to database: {db_error}")
            
        return False, text, image_url, error_message

def get_post_history(limit=20):
    """Return post history from database
    Returns the most recent posts from the database, or in-memory history as fallback
    """
    try:
        # Try to get posts from database
        posts = Post.query.order_by(Post.timestamp.desc()).limit(limit).all()
        
        if posts:
            return [post.to_dict() for post in posts]
        
        # If no posts in database, use in-memory history
        return post_history[:limit] if post_history else []
        
    except Exception as e:
        logger.error(f"Error getting post history: {e}")
        # Fallback to in-memory history on database error
        return post_history[:limit] if post_history else []

def get_random_topic():
    """Get a random topic for post generation that wasn't used recently"""
    try:
        # Load custom topics if they exist
        custom_topics = []
        try:
            if os.path.exists('custom_topics.txt'):
                with open('custom_topics.txt', 'r', encoding='utf-8') as f:
                    custom_topics = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            logger.error(f"Error loading custom topics: {e}")
        
        # Combine built-in and custom topics
        all_topics = TRADING_TOPICS + custom_topics
        
        # Get recent post themes to avoid repetition
        recent_posts = get_post_history(10)
        recent_themes = [post.get('theme') for post in recent_posts if post.get('theme')]
        
        # Filter out recently used topics
        available_topics = [topic for topic in all_topics if topic not in recent_themes]
        
        # If all topics were used recently, use the full list
        if not available_topics:
            available_topics = all_topics
        
        # Select a random topic
        selected_topic = random.choice(available_topics)
        logger.info(f"Selected random topic: {selected_topic}")
        
        return selected_topic
    
    except Exception as e:
        logger.error(f"Error getting random topic: {e}")
        # Fallback to simple random choice from built-in topics
        return random.choice(TRADING_TOPICS)