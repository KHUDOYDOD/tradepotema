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
        "📣 Предупреждающие знаки перетрейдинга: когда нужно остановиться",
        "🚷 Зоны высокого риска: ситуации, когда лучше не входить в рынок",
        "🔔 Системные ошибки начинающих: разбор фатальных заблуждений"
    ]
}

# Combine all categories into one list for easier access
TRADING_TOPICS = []
for category, topics in TRADING_TOPICS_BY_CATEGORY.items():
    TRADING_TOPICS.extend(topics)
for category, topics in EMOTIONAL_TOPICS_BY_CATEGORY.items():
    TRADING_TOPICS.extend(topics)

# Define image categories
TRADING_IMAGES = {
    "charts": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236e3?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1642790551116-304db6618f12?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1559526324-593bc073d938?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1569025690938-a00729c9e1f9?q=80&w=1000&auto=format&fit=crop"
    ],
    "crypto": [
        "https://images.unsplash.com/photo-1621761191319-c6fb62004040?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1624387312873-5f1d60cf7e5c?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1639322537504-6427a16b0a28?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1621504450181-5d356f61d307?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1625217527288-83595e7214c8?q=80&w=1000&auto=format&fit=crop"
    ],
    "stocks": [
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236e3?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1559526324-593bc073d938?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1560221328-12fe60f83ab8?q=80&w=1000&auto=format&fit=crop"
    ],
    "trading_setup": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1611174743420-3d7df880ce32?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1461773518188-b3e86f98242f?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1593062096033-9a26b09da705?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?q=80&w=1000&auto=format&fit=crop"
    ],
    "business": [
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1591696205602-2f950c417cb9?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1579532537598-459ecdaf39cc?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1553729459-efe14ef6055d?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1444653614773-995cb1ef9efa?q=80&w=1000&auto=format&fit=crop"
    ],
    "motivation": [
        "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1596720426673-e4e14290f0cc?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1552664730-d307ca884978?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1533073526757-2c8ca1df9f1c?q=80&w=1000&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?q=80&w=1000&auto=format&fit=crop"
    ]
}

def generate_post_text(prompt=None, emotion="motivational"):
    """Generate text content using OpenRouter's GPT-4 or Claude
    
    Args:
        prompt (str, optional): Тема поста
        emotion (str, optional): Эмоциональный тон (motivational, educational, analytical, cautionary)
    """
    try:
        if not prompt:
            # If no prompt specified, return general advice
            return "📊 Важное напоминание для трейдеров: всегда следуйте своей торговой стратегии и управляйте рисками. #трейдинг #биржа #инвестиции"
        
        # The API key should be set in environment variables
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API key is not set")
            
            # Создаем разные наборы текстов для разных эмоциональных тонов
            fallback_by_emotion = {
                "motivational": [
                    "🚀 Ваше финансовое будущее создается сегодняшними решениями. Инвестируйте с умом, следуйте стратегии и результаты не заставят себя ждать. #трейдинг #прибыль #tradepo",
                    "💪 Трейдинг — это марафон, а не спринт. Каждый день делайте шаг вперед, даже если рынок идет в сторону. Постоянство — ключ к успеху. #трейдинг #успех #tradepo",
                    "⭐ Великие трейдеры отличаются не отсутствием ошибок, а умением извлекать из них уроки. Превратите каждую неудачу в ступеньку к успеху. #трейдинг #развитие #tradepo"
                ],
                "educational": [
                    "📊 Технический анализ раскрывает психологию рынка через графики. Изучайте паттерны, они повторяются, потому что человеческие эмоции неизменны. #трейдинг #техническийанализ #tradepo",
                    "📚 Фундаментальный анализ помогает понять, ЧТО покупать, а технический — КОГДА. Комбинируйте оба подхода для принятия взвешенных решений. #трейдинг #анализ #tradepo",
                    "🧮 Управление капиталом важнее прогнозирования рынка. Определите размер позиции исходя из риска, который готовы принять на каждую сделку. #трейдинг #капитал #tradepo"
                ],
                "analytical": [
                    "📈 Корреляция между активами меняется со временем. Регулярно анализируйте взаимосвязи в своем портфеле для эффективной диверсификации. #трейдинг #анализ #tradepo",
                    "🔍 Объем торгов подтверждает силу тренда. Растущий тренд с увеличивающимся объемом имеет больше шансов на продолжение. #трейдинг #объем #tradepo",
                    "📉 Рынок проводит 80% времени в боковом движении и только 20% в направленном тренде. Адаптируйте стратегии к текущим условиям. #трейдинг #стратегия #tradepo"
                ],
                "cautionary": [
                    "⚠️ Не рискуйте деньгами, которые не можете позволить себе потерять. Сохранение капитала — первое правило успешного трейдинга. #трейдинг #риски #tradepo",
                    "🛑 Эмоциональные решения — главный враг трейдера. Всегда следуйте плану и никогда не торгуйте под влиянием страха или жадности. #трейдинг #психология #tradepo",
                    "⛔ Помните о черных лебедях — непредвиденных событиях, которые могут радикально изменить рынок. Всегда имейте план действий в кризисных ситуациях. #трейдинг #защита #tradepo"
                ]
            }
            
            # Выбираем соответствующий набор текстов по эмоциональному тону
            fallback_texts = fallback_by_emotion.get(emotion, fallback_by_emotion["motivational"])
            
            # Создаем детерминированный, но разнообразный способ выбора текста в зависимости от темы
            if prompt:
                # Используем хеш от темы для выбора текста, чтобы для одной темы всегда был один текст
                index = sum(ord(c) for c in prompt) % len(fallback_texts)
                selected_text = fallback_texts[index]
                # Добавляем хэштег темы
                theme_hashtag = f"#{prompt.replace(' ', '')}"
                return f"{selected_text} {theme_hashtag}"
            else:
                return random.choice(fallback_texts)
            
        headers = {
            "HTTP-Referer": "https://replit.com",  # Add referer for OpenRouter
            "X-Title": "TRADEPO Bot",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Адаптируем промпт в зависимости от эмоционального тона
        emotional_tone_descriptions = {
            "motivational": "вдохновляющий и мотивирующий. Используй энергичный стиль, вдохновляй трейдеров на действия и подчеркивай возможности для успеха.",
            "educational": "образовательный и информативный. Делись ценными знаниями, объясняй сложные концепции простым языком, давай практические советы.",
            "analytical": "аналитический и объективный. Приводи факты, цифры, логические аргументы. Анализируй ситуацию с разных сторон, сохраняя нейтральный тон.",
            "cautionary": "предупреждающий о рисках. Обращай внимание на возможные опасности, подчеркивай важность осторожности, предлагай способы минимизации рисков."
        }
        
        emotional_tone = emotional_tone_descriptions.get(emotion, emotional_tone_descriptions["motivational"])
        
        # Expand prompt to make it more substantial
        user_prompt = prompt
        current_time = datetime.datetime.now()
        
        # Короткий запрос для преодоления ограничения по токенам
        content_request = f"Напиши короткий пост о {user_prompt}. Начни с эмодзи. Добавь #трейдинг #tradepo"
            
        data = {
            "model": "anthropic/claude-3-haiku",  # Use more accessible model
            "messages": [
                {"role": "system", "content": "Ты - опытный финансовый аналитик и эксперт по трейдингу. Твой стиль письма - авторитетный и полезный. Создавай уникальный контент."},
                {"role": "user", "content": content_request}
            ],
            "max_tokens": 30,  # Строгое ограничение токенов из-за лимитов API
            "temperature": 0.8  # Increase for more variety
        }
            
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generating text, attempt {attempt+1}")
                response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=data, headers=headers, timeout=60)
                response.raise_for_status()
                
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
        
        # Подробные тексты для разных тем, чтобы обойти ограничения API
        detailed_fallback_texts = {
            "технический анализ": [
                "📊 **Технический анализ для успешного трейдинга**\n\nПомните, что паттерн «голова и плечи» формируется на протяжении недель и требует подтверждения объемом. При работе с этой фигурой оптимально устанавливать стоп-лосс на 5-7% выше линии шеи, а целевую прибыль рассчитывать как высоту от макушки до линии шеи. В 75% случаев эта стратегия приносит 2R+ дохода. #техническийанализ #трейдинг #tradepo",
                "📈 **Использование индикаторов в трейдинге**\n\nЗнали ли вы, что RSI в 80% случаев дает ложные сигналы в сильных трендах? Профессионалы используют RSI с периодом 14 только в диапазонах, добавляя EMA(200) для фильтрации сигналов. В боковике уровни перекупленности (70+) и перепроданности (30-) действительно работают, давая до 68% прибыльных сделок. #RSI #трейдинг #tradepo",
                "🕯️ **Секреты японских свечей**\n\nМолот и повешенный — это разворотные свечные паттерны с точностью до 65% на дневных графиках. Ключевое отличие: молот формируется на дне и имеет зеленое тело, повешенный — на вершине с красным телом. Для подтверждения сигнала обязательно дождитесь закрытия следующей свечи в направлении разворота и рост объема на 20%+. #свечныйанализ #трейдинг #tradepo"
            ],
            "фундаментальный анализ": [
                "💼 **Фундаментальный анализ для инвестора**\n\nДенежный поток (FCF) — важнейший показатель финансового здоровья компании. В отличие от прибыли, его сложнее манипулировать. Исторически компании с растущим FCF в течение 5+ лет показывают доходность на 12% выше рынка. Ищите бизнесы с конверсией FCF/выручка выше 15% и стабильным ростом этого показателя. #инвестиции #трейдинг #tradepo",
                "📑 **Мультипликаторы в оценке акций**\n\nСопоставляйте P/E компании не только с аналогами, но и с темпами роста. Правило Линча: справедливое P/E примерно равно темпу роста прибыли. Компании с P/E/G < 1 считаются недооцененными, особенно если ROE > 15% и долговая нагрузка Net Debt/EBITDA < 2. Исторически такие компании опережают рынок на 8-12% годовых. #акции #трейдинг #tradepo",
                "🌐 **Геополитика и рынки**\n\nВ среднем рынки отыгрывают геополитические шоки за 13 недель (исследование Ned Davis Research). Выборы повышают волатильность на 18-22% в среднем, а самый сильный рост наблюдается в 3-й год президентского цикла. Монетарная политика влияет на рынки сильнее, чем политические события: изменение ставки ФРС на 25 б.п. в среднем двигает индексы на 2-3%. #геополитика #трейдинг #tradepo"
            ],
            "психология трейдинга": [
                "🧠 **Психология трейдинга: преодоление страха потерь**\n\nИсследования показывают, что трейдеры ощущают потери в 2,5 раза острее, чем прибыль того же размера (эффект Канемана-Тверски). Практикуйте «правило трех убытков»: после 3 последовательных проигрышных сделок делайте паузу на 24 часа и уменьшайте размер позиций на 50%. Это сохранит до 31% депозита в период просадок. #психологиятрейдинга #трейдинг #tradepo",
                "⚡ **Импульсивные решения в трейдинге**\n\nВ среднем трейдеры совершают 5 импульсивных сделок из 10 в состоянии стресса. Решение? Заведите торговый журнал с чек-листом из 5 пунктов для каждой сделки. Исследования показывают, что простой контрольный список снижает количество эмоциональных решений на 42% и повышает общую доходность на 18%. #дисциплина #трейдинг #tradepo",
                "😱 **Синдром упущенной выгоды (FOMO)**\n\nFOMO заставляет трейдеров входить на 22% выше оптимальных точек входа (данные TradeStation). Противоядие: установите конкретные условия входа и придерживайтесь их. Используйте правило 3-6-9: ждите коррекции минимум на 3% в краткосрочных трендах, 6% в среднесрочных и 9% в долгосрочных перед входом в позицию. #FOMO #трейдинг #tradepo"
            ],
            "управление рисками": [
                "📏 **Профессиональное управление капиталом**\n\nИсследования показывают, что 62% успешных трейдеров никогда не рискуют более чем 1-2% капитала на одну сделку. Используйте формулу Келли (оптимальная доля = (шанс выигрыша × коэффициент выигрыша - шанс проигрыша) / коэффициент выигрыша) и умножайте результат на 0.5 для дополнительной защиты. #рискменеджмент #трейдинг #tradepo",
                "🛡️ **Хеджирование позиций**\n\nПортфельное хеджирование опционами стоит в среднем 1-3% годовой доходности, но спасает от 15-30% просадки в кризисы. Оптимальная стратегия: покупка пут-опционов на 5-10% от размера портфеля со страйком 10-15% ниже текущих цен и экспирацией через 60-90 дней. В периоды низкой волатильности (VIX<15) стоимость такой защиты минимальна. #хеджирование #трейдинг #tradepo",
                "🔄 **Антихрупкость торговой системы**\n\nВ периоды высокой волатильности 91% розничных трейдеров теряют деньги из-за отсутствия адаптивного риск-менеджмента. Решение? Динамический стоп-лосс на основе ATR: используйте 2xATR(14) для позиций по тренду и 1xATR(14) для контртрендовых сделок. Исследования показывают, что это сохраняет до 23% больше капитала в турбулентные периоды. #волатильность #трейдинг #tradepo"
            ],
            "криптовалюты": [
                "₿ **Цикличность крипторынка**\n\nИсторически биткоин проходит полный цикл каждые 3.5-4 года, связанный с халвингами. Средняя продолжительность бычьих рынков составляет 12-15 месяцев, медвежьих — 18-24 месяца. После халвинга до пика проходит в среднем 12-18 месяцев, с ROI от низа до пика в 10-25x. Лучшая стратегия — накопление в последней трети медвежьего рынка. #биткоин #трейдинг #tradepo",
                "⛓️ **On-chain анализ криптовалют**\n\nМетрика SOPR (Spent Output Profit Ratio) с точностью до 72% определяет ключевые развороты на рынке BTC. Значения ниже 1 в течение 30+ дней исторически указывали на дно, а устойчивые значения выше 1.5 — на пик. Дополните анализ метрикой MVRV-Z Score: значения ниже 0 сигнализируют о недооценке, выше 7 — о перегреве рынка. #криптоанализ #трейдинг #tradepo",
                "🪙 **Фундаментальный анализ токенов**\n\nПри отборе альткоинов оценивайте токеномику: здоровая инфляция (эмиссия) — не более 10-15% в год, распределение токенов — команда и инсайдеры должны владеть не более 30-40%. Блокировка (vesting) минимум 2-3 года для команды критически важна. Проекты с соотношением FDV/TVL < 2 для DeFi или P/S < 10 для инфраструктурных решений статистически показывают лучшую долгосрочную динамику. #альткоины #трейдинг #tradepo"
            ]
        }
        
        # Простые тексты для случайных тем или эмоциональных состояний
        fallback_texts = [
            "📊 Важное напоминание: анализируйте рынок перед каждой сделкой и следуйте своему торговому плану. Успешный трейдинг строится на дисциплине!",
            "💰 Трейдинг — это марафон, а не спринт. Разработайте стратегию, которая соответствует вашим целям и временным горизонтам.",
            "📈 Управление рисками — фундамент успешного трейдинга. Никогда не вкладывайте в одну сделку больше, чем можете позволить себе потерять.",
            "💼 Помните, что в рыночных колебаниях скрыты возможности. Профессионалы видят перспективы там, где другие паникуют.",
            "🧠 Психологическая устойчивость — ваше главное преимущество на рынке. Развивайте эмоциональный контроль и дисциплину.",
            "📱 Технологии изменили рынки навсегда. Используйте современные инструменты анализа, чтобы оставаться на шаг впереди.",
            "🔍 Фундаментальный анализ помогает понять, ЧТО покупать, технический анализ подсказывает, КОГДА это делать.",
            "⚡ Рыночные тренды могут длиться дольше, чем вы рассчитываете. Не спешите против течения без веских причин."
        ]
        
        # Use the theme as a seed for randomization to ensure different themes get different texts
        # but the same theme consistently gets the same text within a session
        seed = sum(ord(c) for c in prompt) if prompt else 0
        random.seed(seed + time.time())  # Add time to ensure variation even for the same theme
        
        # Попробуем найти подробный текст по теме
        theme_lower = prompt.lower() if prompt else ""
        
        # Поиск по ключевым словам в теме
        for category, texts in detailed_fallback_texts.items():
            category_keywords = {
                "технический анализ": ["технический", "анализ", "индикатор", "график", "свечи", "паттерн", "трейд"],
                "фундаментальный анализ": ["фундаментальный", "анализ", "отчетность", "компани", "макро", "экономи"],
                "психология трейдинга": ["психолог", "эмоц", "страх", "дисциплин", "психологич", "страте"],
                "управление рисками": ["риск", "управлен", "стоп", "лосс", "капитал", "позиц", "хедж"],
                "криптовалюты": ["крипт", "биткоин", "блокчейн", "альткоин", "токен", "майнинг"]
            }
            
            keywords = category_keywords.get(category, [])
            for keyword in keywords:
                if keyword in theme_lower:
                    # Нашли совпадение по категории, возвращаем детальный текст
                    return random.choice(texts)
        
        # Если не нашли подходящую категорию, используем обычный fallback
        fallback_text = random.choice(fallback_texts)
        
        # Add hashtags and theme-specific hashtag
        theme_hashtag = f"#{prompt.replace(' ', '')}" if prompt else "#трейдинг"
        return f"{fallback_text} {theme_hashtag} #трейдинг #tradepo"

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
        text = generate_post_text(theme, emotion)
        
        # Get thematically relevant image URL based on the post content
        image_url = get_image_url_by_theme(theme, emotion)
        
        # Make sure we have a valid image URL - это хорошая практика, чтобы предотвратить ошибки Telegram API
        if not image_url or not image_url.startswith(('http://', 'https://')):
            # Если URL изображения некорректный, используем надежные запасные URL
            fallback_images = [
                "https://images.unsplash.com/photo-1611974789855-9c2a0a7236e3?q=80&w=1000&auto=format&fit=crop",  # Торговый график
                "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?q=80&w=1000&auto=format&fit=crop",  # Бизнес
                "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?q=80&w=1000&auto=format&fit=crop"   # Технологии
            ]
            image_url = fallback_images[hash(theme) % len(fallback_images)]
            logger.warning(f"Using fallback image URL: {image_url}")
        
        # Проверим URL изображения через HEAD-запрос, чтобы убедиться, что оно доступно
        try:
            response = requests.head(image_url, timeout=5)
            if response.status_code != 200:
                raise Exception(f"Image URL returned status code {response.status_code}")
        except Exception as img_error:
            logger.error(f"Error checking image URL: {img_error}")
            # Если URL некорректный, используем гарантированно надежный запасной URL
            image_url = "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?q=80&w=1000&auto=format&fit=crop"
            logger.warning(f"Using emergency fallback image URL after check failed")
        
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

def get_random_topic(emotion=None):
    """Get a random topic for post generation that wasn't used recently
    
    Args:
        emotion (str, optional): Эмоциональный тон для подбора тематической темы
    """
    try:
        # Load custom topics if they exist
        custom_topics = []
        try:
            if os.path.exists('custom_topics.txt'):
                with open('custom_topics.txt', 'r', encoding='utf-8') as f:
                    custom_topics = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            logger.error(f"Error loading custom topics: {e}")
        
        # Если указан эмоциональный тон, предпочитаем темы из соответствующей категории
        if emotion:
            # Сопоставляем эмоции с категориями тем
            emotion_topic_map = {
                "motivational": "Мотивационные",
                "educational": "Технический анализ",
                "analytical": "Фундаментальный анализ",
                "cautionary": "Управление рисками"
            }
            
            # Если есть соответствующая категория, берем из неё темы
            category = emotion_topic_map.get(emotion)
            if category and category in EMOTIONAL_TOPICS_BY_CATEGORY:
                category_topics = EMOTIONAL_TOPICS_BY_CATEGORY[category]
                thematic_topics = category_topics
            else:
                # Если нет соответствующей категории, используем все доступные темы
                thematic_topics = TRADING_TOPICS
        else:
            # Если эмоция не указана, используем все доступные темы
            thematic_topics = TRADING_TOPICS
        
        # Combine built-in and custom topics
        all_topics = thematic_topics + custom_topics
        
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
        
def analyze_post_performance(post_id=None, days=30):
    """Анализирует эффективность постов на основе истории публикаций
    
    Args:
        post_id (int, optional): ID конкретного поста для анализа
        days (int, optional): Период анализа в днях
        
    Returns:
        dict: Статистика постов
    """
    try:
        if post_id:
            # Анализ одного конкретного поста
            try:
                post = Post.query.filter_by(id=post_id).first()
                if not post:
                    return {"error": f"Пост с ID {post_id} не найден"}
                
                return {
                    "post_id": post.id,
                    "theme": post.theme,
                    "timestamp": post.timestamp.isoformat(),
                    "success": post.success,
                    "processing_time": post.processing_time,
                    "text_length": len(post.full_text) if post.full_text else 0
                }
            except Exception as e:
                logger.error(f"Error analyzing post {post_id}: {e}")
                return {"error": f"Ошибка анализа поста: {str(e)}"}
        else:
            # Анализ всех постов за указанный период
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            
            try:
                # Получаем все посты за период
                posts = Post.query.filter(Post.timestamp >= cutoff_date).all()
                
                if not posts:
                    return {"error": f"Нет постов за последние {days} дней"}
                
                # Собираем статистику
                total_posts = len(posts)
                successful_posts = sum(1 for p in posts if p.success)
                failed_posts = total_posts - successful_posts
                
                # Считаем среднюю длину текста
                text_lengths = [len(p.full_text) if p.full_text else 0 for p in posts]
                avg_text_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
                
                # Анализируем используемые темы
                themes = {}
                for post in posts:
                    if post.theme:
                        themes[post.theme] = themes.get(post.theme, 0) + 1
                
                # Находим самые популярные темы
                popular_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:5]
                
                # Анализируем время обработки
                processing_times = []
                for post in posts:
                    if post.processing_time:
                        try:
                            # Обрабатываем формат "X.XXs"
                            time_str = post.processing_time.replace("s", "")
                            processing_times.append(float(time_str))
                        except:
                            pass
                
                avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
                
                return {
                    "period_days": days,
                    "total_posts": total_posts,
                    "successful_posts": successful_posts,
                    "failed_posts": failed_posts,
                    "success_rate": f"{(successful_posts / total_posts * 100):.1f}%" if total_posts > 0 else "0%",
                    "avg_text_length": f"{avg_text_length:.1f} символов",
                    "avg_processing_time": f"{avg_processing_time:.2f} сек.",
                    "popular_themes": popular_themes,
                    "posts_per_day": f"{total_posts / days:.1f}"
                }
                
            except Exception as e:
                logger.error(f"Error analyzing posts: {e}")
                return {"error": f"Ошибка анализа постов: {str(e)}"}
                
    except Exception as e:
        logger.error(f"Error in analyze_post_performance: {e}")
        return {"error": f"Внутренняя ошибка: {str(e)}"}

def generate_post_summary(theme, emotion="motivational"):
    """Генерирует краткую версию поста для предпросмотра
    
    Args:
        theme (str): Тема поста
        emotion (str, optional): Эмоциональный тон
        
    Returns:
        dict: Предварительный вариант поста с текстом и URL изображения
    """
    try:
        # Генерируем краткую версию текста
        prompt = f"Тема: {theme} (тон: {emotion})"
        text = generate_post_text(theme, emotion)
        
        # Получаем URL изображения
        image_url = get_image_url_by_theme(theme, emotion)
        
        # Формируем результат
        return {
            "theme": theme,
            "emotion": emotion,
            "text": text,
            "text_preview": text[:100] + "..." if len(text) > 100 else text,
            "image_url": image_url,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error generating post summary: {e}")
        return {
            "theme": theme,
            "emotion": emotion,
            "error": format_error_for_display(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

def check_image_url(url):
    """Проверяет доступность URL изображения
    
    Args:
        url (str): URL для проверки
        
    Returns:
        bool: True если изображение доступно, иначе False
    """
    try:
        if not url or not url.startswith(('http://', 'https://')):
            return False
            
        response = requests.head(url, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error checking image URL {url}: {e}")
        return False