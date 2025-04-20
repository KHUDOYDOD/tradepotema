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

# Детальные темы для трейдинга по категориям
TRADING_TOPICS_BY_CATEGORY = {
    "Технический анализ": [
        "🔮 Фигуры технического анализа: как распознать и использовать для входа в рынок",
        "📈 Скользящие средние: настройка и стратегии торговли на пересечениях",
        "📊 Объемные индикаторы в трейдинге: как определить силу тренда",
        "🎯 Технические индикаторы перекупленности и перепроданности: стратегии использования",
        "🧮 Фибоначчи в трейдинге: уровни коррекции и расширения",
        "🕯️ Паттерны японских свечей: что они говорят о рыночном настроении",
        "📋 Как читать ленту сделок и стакан заявок: тактики внутридневной торговли",
        "📉 Индикатор RSI: оптимальные настройки и торговые сигналы",
        "🔄 Дивергенции в техническом анализе: поиск разворотных моментов",
        "🌊 Волновой анализ Эллиотта: прогнозирование движения рынка"
    ],
    "Фундаментальный анализ": [
        "📑 Анализ финансовой отчетности: на что обращать внимание трейдеру",
        "🌍 Макроэкономические показатели и их влияние на рынки: календарь трейдера",
        "🏭 Отраслевой анализ: как выбирать перспективные секторы для инвестиций",
        "💹 Мультипликаторы в оценке акций: P/E, P/B, EV/EBITDA и другие",
        "📢 Корпоративные события: как торговать на отчетностях, дивидендах и сплитах",
        "💲 Процентные ставки и их влияние на различные классы активов",
        "🌐 Геополитические факторы и их воздействие на финансовые рынки",
        "🦾 Анализ конкурентных преимуществ компании для долгосрочных инвестиций",
        "👨‍💼 Инсайдерские сделки: как отслеживать действия руководства компаний",
        "💵 Денежные потоки компании как индикатор инвестиционной привлекательности"
    ],
    "Психология трейдинга": [
        "🧠 Эмоциональный интеллект трейдера: как управлять страхом и жадностью",
        "🎭 Психологические ловушки на рынке: когнитивные искажения в принятии решений",
        "⚓ Развитие дисциплины: как следовать торговому плану в любых условиях",
        "🧘‍♂️ Управление стрессом: техники сохранения ясности мышления в волатильные периоды",
        "❌ Психология убытков: как правильно реагировать на проигрышные сделки",
        "💡 Ментальные модели успешных трейдеров: мышление в вероятностных категориях",
        "⚡ Импульсивная торговля: причины и методы преодоления",
        "⚖️ Психологические аспекты масштабирования позиций: когда увеличивать риск",
        "😱 Синдром упущенной выгоды (FOMO): как с ним бороться",
        "🛡️ Формирование психологической устойчивости: практики для трейдеров"
    ],
    "Управление рисками": [
        "📏 Позиционный сайзинг: методы расчета оптимального размера позиции",
        "🚫 Стоп-лоссы и тейк-профиты: стратегии установки и корректировки",
        "🔗 Корреляция активов: как строить диверсифицированный портфель",
        "📊 Управление волатильностью: торговые стратегии для разных рыночных условий",
        "🧮 Расчет математического ожидания: оценка долгосрочной прибыльности",
        "🛡️ Хеджирование позиций: инструменты и техники защиты портфеля",
        "⛓️ Каскадные стоп-приказы: защита прибыли при сильных движениях",
        "💸 Риск-менеджмент при торговле с плечом: особенности и правила",
        "🔄 Антифрагильность торговой системы: адаптация к изменениям рынка",
        "🧪 Сценарный анализ и стресс-тесты для торговых стратегий"
    ],
    "Криптовалюты": [
        "🖼️ NFT-рынок: тренды, возможности и риски для инвесторов",
        "🏦 DeFi-протоколы: стратегии заработка на децентрализованных финансах",
        "₿ Технический анализ биткоина: особенности и ключевые уровни",
        "⛓️ Анализ блокчейн-метрик: on-chain индикаторы для трейдеров",
        "🪙 Альткоины: методология отбора перспективных проектов",
        "💱 Токеномика проектов: как оценивать долгосрочный потенциал криптовалют",
        "📱 Фундаментальный анализ криптопроектов: технологии или сообщество?",
        "🔄 Циклы криптовалютного рынка: как определять фазы и торговать в соответствии с ними",
        "⛏️ Майнинг и стейкинг: пассивные стратегии заработка на криптовалюте",
        "🐋 Институциональные инвесторы в крипте: отслеживание китов и анализ их влияния"
    ]
}

# Эмоциональные темы с эмодзи по категориям
EMOTIONAL_TOPICS_BY_CATEGORY = {
    "Мотивационные": [
        "🔥 Как разогнать депозит: стратегии агрессивного роста капитала",
        "💰 Секреты миллионеров: как мыслят успешные трейдеры",
        "🚀 От новичка до профи: путь успешного трейдера за 12 месяцев",
        "⚡ Психология богатства: как мыслить категориями прибыли и возможностей",
        "💎 Трейдинг как стиль жизни: путь к финансовой свободе и независимости",
        "🏆 10 привычек успешных трейдеров, которые меняют игру",
        "💪 Как преодолеть страх и принимать смелые торговые решения",
        "✨ Визуализация успеха: ментальные техники притяжения прибыли",
        "🔮 Управление судьбой: как трейдинг меняет жизненную траекторию",
        "⭐ Формула личной эффективности: как достичь большего, торгуя меньше"
    ],
    "Образовательные": [
        "📚 Фундамент успешного трейдинга: 7 принципов, о которых молчат гуру",
        "🧠 Нейропластичность трейдера: как тренировать мозг для анализа рынка",
        "📊 Методология построения торговой системы с нуля",
        "🔍 Скрытые индикаторы рынка: на что смотрят профессионалы",
        "📝 Торговый журнал мастера: как анализировать свои сделки правильно",
        "📱 Мобильный трейдинг: комплексное руководство по торговле с телефона",
        "🎓 Академия успешного инвестора: от теории к практике",
        "💻 Автоматизация торговли: создаем бота без навыков программирования",
        "🔎 Глубокий анализ рынка: методы профессиональных аналитиков",
        "📌 Критические точки входа: как выбирать идеальный момент для сделки"
    ],
    "Аналитические": [
        "📈 Межрыночные корреляции: комплексный подход к анализу активов",
        "📉 Циклы волатильности и их использование в торговых стратегиях",
        "🧮 Квантитативный анализ: применение математических моделей в трейдинге",
        "🧩 Поведенческие паттерны рынка: как распознавать и использовать",
        "📊 Объемный профиль и анализ ликвидности: взгляд в глубину рынка",
        "🔢 Индикаторы волатильности и моментума: синергия в алгоритме",
        "📡 Рыночные аномалии: исследование и стратегии монетизации",
        "📑 Факторное инвестирование: построение робастных стратегий",
        "🔬 Микроструктура рынка: анализ ордербука и потока ордеров",
        "📋 Сезонность на финансовых рынках: статистический анализ и применение"
    ],
    "Предупреждающие": [
        "⚠️ Скрытые риски маржинальной торговли: что нужно знать каждому",
        "🛑 Психологические ловушки трейдинга: как не потерять всё",
        "⛔ Манипуляции на рынке: как распознать и защититься",
        "🔴 Burnout трейдера: признаки и методы предотвращения",
        "🚨 Тревожные сигналы рынка: индикаторы приближающегося краха",
        "⏰ Тайм-киллеры трейдера: как перестать терять время и деньги",
        "🧯 Экстренные меры при обвале рынка: план действий",
        "🚧 Юридические риски трейдинга: что нужно знать о регулировании",
        "🔒 Кибербезопасность для трейдеров: защита счетов и личных данных",
        "📣 Предупреждающие знаки перетрейдинга: когда нужно остановиться"
    ]
}

# Объединить все темы в один список для обратной совместимости
TRADING_TOPICS = []
for category, topics in TRADING_TOPICS_BY_CATEGORY.items():
    TRADING_TOPICS.extend(topics)
for category, topics in EMOTIONAL_TOPICS_BY_CATEGORY.items():
    TRADING_TOPICS.extend(topics)

# Trading-related images by category - популярные изображения по темам для трейдинга
TRADING_IMAGES = {
    "charts": [
        "https://images.unsplash.com/photo-1535320903710-d993d3d77d29",
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3",
        "https://images.unsplash.com/photo-1548094878-84ced0f6896d",
        "https://images.unsplash.com/photo-1543286386-713bdd548da4",
        "https://images.unsplash.com/photo-1569025690938-a00729c9e1f9"
    ],
    "crypto": [
        "https://images.unsplash.com/photo-1518546305927-5a555bb7020d",
        "https://images.unsplash.com/photo-1516245834210-c4c142787335",
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f",
        "https://images.unsplash.com/photo-1622630998477-20aa696ecb05",
        "https://images.unsplash.com/photo-1625217527288-83595e7214c8"
    ],
    "stocks": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3",
        "https://images.unsplash.com/photo-1559526324-593bc073d938",
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e",
        "https://images.unsplash.com/photo-1560221328-12fe60f83ab8"
    ],
    "trading_setup": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71",
        "https://images.unsplash.com/photo-1611174743420-3d7df880ce32",
        "https://images.unsplash.com/photo-1461773518188-b3e86f98242f",
        "https://images.unsplash.com/photo-1593062096033-9a26b09da705",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf"
    ],
    "business": [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f",
        "https://images.unsplash.com/photo-1591696205602-2f950c417cb9",
        "https://images.unsplash.com/photo-1579532537598-459ecdaf39cc",
        "https://images.unsplash.com/photo-1553729459-efe14ef6055d",
        "https://images.unsplash.com/photo-1444653614773-995cb1ef9efa"
    ],
    "motivation": [
        "https://images.unsplash.com/photo-1492366254240-43affaefc3e3",
        "https://images.unsplash.com/photo-1504805572947-34fad45aed93",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab",
        "https://images.unsplash.com/photo-1519834022362-8c5d61c9c64b",
        "https://images.unsplash.com/photo-1507936580189-3816b4656daa"
    ]
}

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

def get_image_url_by_theme(theme="", emotion="motivational"):
    """Get an image URL that matches the post theme
    
    Args:
        theme (str): Тема поста
        emotion (str): Эмоциональный тон поста
    
    Returns:
        str: URL изображения
    """
    # Try to get image from custom image list first
    custom_image = get_image_from_file()
    if custom_image:
        return custom_image
    
    # Determine best category based on theme keywords
    theme_lower = theme.lower() if theme else ""
    
    # Keywords that indicate which category to use
    category_keywords = {
        "charts": ["график", "тренд", "индикатор", "технический", "анализ", "свечи", "паттерн", "фигуры"],
        "crypto": ["крипто", "биткоин", "альткоин", "nft", "блокчейн", "токен", "майнинг", "стейкинг"],
        "stocks": ["акции", "фондовый", "ценные бумаги", "дивиденды", "опцион", "фьючерс", "долгосрочн"],
        "trading_setup": ["рабочее место", "терминал", "платформа", "скальпинг", "дейтрейдинг"],
        "business": ["бизнес", "карьера", "профессионал", "инвестиции", "доход", "капитал", "портфель"],
        "motivation": ["психология", "успех", "мотивация", "дисциплина", "мышление", "развитие", "стратегия"]
    }
    
    # Check for keywords in theme
    matching_categories = []
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in theme_lower:
                matching_categories.append(category)
                break
    
    # Map emotion to image category if no matching keywords found
    emotion_to_category = {
        "motivational": ["motivation", "business"],
        "educational": ["charts", "trading_setup"],
        "analytical": ["charts", "stocks"],
        "cautionary": ["stocks", "business"]
    }
    
    # If no matching categories, use emotion mapping or default to charts
    if not matching_categories:
        emotion_categories = emotion_to_category.get(emotion, ["charts"])
        category = random.choice(emotion_categories)
    else:
        category = random.choice(matching_categories)
    
    # Get images for the category
    category_images = TRADING_IMAGES.get(category, TRADING_IMAGES["charts"])
    
    # Return a random image from the category
    return random.choice(category_images)

def get_image_from_file():
    """Get a random image URL from the image_urls.txt file"""
    try:
        if os.path.exists('image_urls.txt'):
            with open('image_urls.txt', 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f.readlines() if line.strip()]
                
            if urls:
                return random.choice(urls)
                
    except Exception as e:
        logger.error(f"Error getting image URL from file: {e}")
        
    # Return None if no custom image is available
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

def create_and_send_post(theme, emotion="motivational"):
    """Create and send a post to the Telegram channel
    
    Args:
        theme (str): Тема поста
        emotion (str, optional): Эмоциональный тон (motivational, educational, analytical, cautionary)
    """
    start_time = time.time()
    success = False
    text = None
    image_url = None
    result = None
    error = None
    
    try:
        logger.info(f"Creating post with theme: {theme}, emotion: {emotion}")
        
        # Generate text for the post using the specified emotion
        text = generate_post_text(theme)
        
        # Get thematically relevant image URL based on the post content
        image_url = get_image_url_by_theme(theme, emotion)
        
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