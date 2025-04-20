import os
import logging
import datetime
import random
import requests
import importlib
import json
import calendar
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from jinja2 import Environment
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db
from models import Post

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Add custom filter for date and time
@app.template_filter('now')
def filter_now(fmt='%Y'):
    """Return current date/time in specified format"""
    return datetime.datetime.now().strftime(fmt)

# Import modules with circular dependencies after defining app
from bot import create_and_send_post, get_post_history, TRADING_TOPICS, get_random_topic
from utils import get_current_time_formatted, get_current_date_formatted, get_system_status, format_time_for_schedule, TIMEZONE
from scheduler import scheduler

# Настройка Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
login_manager.login_message_category = 'warning'

# Simple User class for authentication
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# User authentication form
class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

# Admin credentials - hardcoded for simplicity
ADMIN_USER = User(
    id=1,
    username='TRADEPO',
    password_hash=generate_password_hash('X12345x')
)

@login_manager.user_loader
def load_user(user_id):
    if int(user_id) == ADMIN_USER.id:
        return ADMIN_USER
    return None

# Constants
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@tradepotrest')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
SCHEDULE_TIMES = ["10:30", "13:30", "15:00", "17:00", "18:30"]
SCHEDULED_POSTS_FILE = 'scheduled_posts.json'

# Start the scheduler when the app starts
def initialize_app():
    if not scheduler.is_running:
        scheduler.start()
        logger.info("Scheduler started on app initialization")

# Use with_appcontext in newer Flask versions
with app.app_context():
    initialize_app()

@app.route('/')
def index():
    """Dashboard home page"""
    # Get current time in the configured timezone
    current_time = get_current_time_formatted()
    current_date = get_current_date_formatted()

    # Get system status
    system_status = get_system_status()

    # Get scheduler status
    scheduler_status = scheduler.get_status()

    # Format schedule times for display
    formatted_schedule_times = [format_time_for_schedule(t) for t in SCHEDULE_TIMES]

    # Get post history
    recent_posts = get_post_history()

    # Select random topics for suggestions
    suggested_topics = random.sample(TRADING_TOPICS, min(5, len(TRADING_TOPICS)))

    # Load custom topics if they exist
    custom_topics = []
    try:
        if os.path.exists('custom_topics.txt'):
            with open('custom_topics.txt', 'r', encoding='utf-8') as f:
                custom_topics = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        logger.error(f"Error loading custom topics: {e}")

    # Load scheduled posts
    scheduled_posts = get_scheduled_posts()

    # Add statistics
    stats = {
        'total_posts': 0,
        'successful_posts': 0,
        'failed_posts': 0,
        'topics_count': len(TRADING_TOPICS) + len(custom_topics),
        'images_count': 0,
        'today_posts': 0,
        'scheduled_posts': len(scheduled_posts),
        'engagement_rate': random.uniform(2.5, 5.5)  # Sample engagement rate
    }

    # Count total posts
    if recent_posts:
        stats['total_posts'] = len(recent_posts)
        stats['successful_posts'] = sum(1 for post in recent_posts if post.get('success', False))
        stats['failed_posts'] = stats['total_posts'] - stats['successful_posts']

        # Count today's posts
        today = datetime.datetime.now().date()
        stats['today_posts'] = sum(1 for post in recent_posts 
                                 if datetime.datetime.fromisoformat(post.get('timestamp', '')).date() == today)

    # Count images
    try:
        if os.path.exists('image_urls.txt'):
            with open('image_urls.txt', 'r', encoding='utf-8') as f:
                stats['images_count'] = sum(1 for line in f if line.strip())
    except Exception as e:
        logger.error(f"Error counting images: {e}")

    # Generate analytics data for chart
    analytics_data = generate_analytics_data(recent_posts)

    return render_template(
        'index.html',
        channel_id=CHANNEL_ID,
        timezone_name=TIMEZONE.zone,
        current_time=current_time,
        current_date=current_date,
        schedule_times=formatted_schedule_times,
        system_status=system_status,
        scheduler_status=scheduler_status,
        suggested_topics=suggested_topics,
        custom_topics=custom_topics,
        recent_posts=recent_posts,
        scheduled_posts=scheduled_posts,
        stats=stats,
        analytics_data=analytics_data
    )

def generate_analytics_data(posts):
    """Generate analytics data for charts"""
    # Posts by day of week
    days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    posts_by_day = [0] * 7
    
    # Posts by hour
    posts_by_hour = [0] * 24
    
    # Success rate over time (last 2 weeks)
    today = datetime.datetime.now().date()
    two_weeks_ago = today - datetime.timedelta(days=14)
    success_rate_dates = []
    success_rate_values = []
    
    # Get day posts counts and success rates for the last 2 weeks
    for i in range(14):
        date = two_weeks_ago + datetime.timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        success_rate_dates.append(date.strftime('%d.%m'))
        
        # Count posts and successful posts for this date
        total_for_day = 0
        successful_for_day = 0
        
        for post in posts:
            try:
                post_date = datetime.datetime.fromisoformat(post.get('timestamp', '')).date()
                if post_date == date:
                    total_for_day += 1
                    if post.get('success', False):
                        successful_for_day += 1
                        
                    # Count by day of week
                    day_of_week = post_date.weekday()  # 0 is Monday
                    posts_by_day[day_of_week] += 1
                    
                    # Count by hour
                    hour = datetime.datetime.fromisoformat(post.get('timestamp', '')).hour
                    posts_by_hour[hour] += 1
            except (ValueError, TypeError):
                continue
        
        # Calculate success rate
        success_rate = (successful_for_day / total_for_day * 100) if total_for_day > 0 else 0
        success_rate_values.append(round(success_rate, 1))
    
    # Return all analytics data
    return {
        'days_of_week': {
            'labels': days_of_week,
            'values': posts_by_day
        },
        'posts_by_hour': {
            'labels': list(range(24)),
            'values': posts_by_hour
        },
        'success_rate': {
            'labels': success_rate_dates,
            'values': success_rate_values
        }
    }

@app.route('/create_post', methods=['POST'])
def create_post():
    """Create and send a post"""
    theme = request.form.get('theme', '').strip()
    save_theme = request.form.get('save_theme') == 'on'
    schedule_post = request.form.get('schedule_post') == 'on'
    schedule_date = request.form.get('schedule_date', '')
    schedule_time = request.form.get('schedule_time', '')
    post_emotion = request.form.get('post_emotion', 'motivational')

    if not theme:
        flash('Пожалуйста, укажите тему поста', 'warning')
        return redirect(url_for('index'))

    # Handle scheduled posts
    if schedule_post and schedule_date and schedule_time:
        try:
            # Parse date and time
            scheduled_datetime = datetime.datetime.strptime(
                f"{schedule_date} {schedule_time}", "%Y-%m-%d %H:%M"
            )
            
            # Check if date is in the future
            if scheduled_datetime <= datetime.datetime.now():
                flash('Дата и время должны быть в будущем', 'warning')
                return redirect(url_for('index'))
                
            # Add to scheduled posts
            add_scheduled_post(theme, scheduled_datetime.isoformat(), post_emotion)
            
            flash(f'Пост на тему "{theme}" запланирован на {schedule_date} {schedule_time}', 'success')
            
            # Save theme if needed
            if save_theme and theme not in TRADING_TOPICS:
                save_custom_topic(theme)
                
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error scheduling post: {e}")
            flash(f'Ошибка при планировании поста: {str(e)}', 'danger')
            return redirect(url_for('index'))

    # Handle immediate post creation
    try:
        # Create and send the post with the selected emotional tone
        success, text, image_url, result = create_and_send_post(theme, post_emotion)

        if success:
            flash(f'Пост на тему "{theme}" успешно отправлен в канал {CHANNEL_ID}.', 'success')

            # Save the theme if user checked the box and it's not already in the list
            if save_theme and theme not in TRADING_TOPICS:
                save_custom_topic(theme)
        else:
            flash(f'Ошибка при отправке поста: {result}', 'danger')

    except Exception as e:
        logger.error(f"Error in create_post route: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')

    return redirect(url_for('index'))

def save_custom_topic(theme):
    """Save a custom topic"""
    try:
        # Create file for storing custom topics if it doesn't exist
        custom_topics_file = 'custom_topics.txt'

        # Create or append to file
        with open(custom_topics_file, 'a', encoding='utf-8') as f:
            f.write(f"{theme}\n")

        flash(f'Тема "{theme}" сохранена в избранное', 'success')

        # Add topic to current topics list
        TRADING_TOPICS.append(theme)
    except Exception as e:
        logger.error(f"Error saving custom theme: {e}")
        flash(f'Ошибка при сохранении темы: {str(e)}', 'danger')

def get_scheduled_posts():
    """Get list of scheduled posts"""
    try:
        if os.path.exists(SCHEDULED_POSTS_FILE):
            with open(SCHEDULED_POSTS_FILE, 'r', encoding='utf-8') as f:
                scheduled_posts = json.load(f)
                
                # Sort by scheduled datetime
                scheduled_posts.sort(key=lambda x: x.get('scheduled_at', ''))
                
                # Filter out posts scheduled in the past
                now = datetime.datetime.now().isoformat()
                scheduled_posts = [post for post in scheduled_posts if post.get('scheduled_at', '') > now]
                
                return scheduled_posts
        return []
    except Exception as e:
        logger.error(f"Error loading scheduled posts: {e}")
        return []

def add_scheduled_post(theme, scheduled_at, emotion="motivational"):
    """Add a post to the scheduled posts list
    
    Args:
        theme (str): Тема поста
        scheduled_at (str): Запланированная дата и время в формате ISO
        emotion (str, optional): Эмоциональный тон поста
    """
    try:
        scheduled_posts = []
        if os.path.exists(SCHEDULED_POSTS_FILE):
            try:
                with open(SCHEDULED_POSTS_FILE, 'r', encoding='utf-8') as f:
                    scheduled_posts = json.load(f)
            except json.JSONDecodeError:
                scheduled_posts = []
                
        # Create a new scheduled post
        new_post = {
            'id': len(scheduled_posts) + 1,
            'theme': theme,
            'scheduled_at': scheduled_at,
            'emotion': emotion,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        scheduled_posts.append(new_post)
        
        # Save to file
        with open(SCHEDULED_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(scheduled_posts, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        logger.error(f"Error adding scheduled post: {e}")
        return False

@app.route('/delete_scheduled_post/<int:post_id>', methods=['POST'])
def delete_scheduled_post(post_id):
    """Delete a scheduled post"""
    try:
        if os.path.exists(SCHEDULED_POSTS_FILE):
            with open(SCHEDULED_POSTS_FILE, 'r', encoding='utf-8') as f:
                scheduled_posts = json.load(f)
                
            # Find and remove the post
            for i, post in enumerate(scheduled_posts):
                if post.get('id') == post_id:
                    del scheduled_posts[i]
                    break
            
            # Save the updated list
            with open(SCHEDULED_POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(scheduled_posts, f, ensure_ascii=False, indent=2)
                
            flash('Запланированный пост удален', 'success')
        else:
            flash('Файл с запланированными постами не найден', 'warning')
    except Exception as e:
        logger.error(f"Error deleting scheduled post: {e}")
        flash(f'Ошибка при удалении запланированного поста: {str(e)}', 'danger')
        
    return redirect(url_for('index'))

@app.route('/create_random_post')
def create_random_post():
    """Create and send a post with random topic"""
    try:
        # Get random topic
        topic = get_random_topic()

        # Create and send the post
        success, text, image_url, result = create_and_send_post(topic)

        if success:
            flash(f'Пост на тему "{topic}" успешно отправлен в канал {CHANNEL_ID}.', 'success')
        else:
            flash(f'Ошибка при отправке поста: {result}', 'danger')

    except Exception as e:
        logger.error(f"Error in create_random_post route: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')

    return redirect(url_for('index'))

@app.route('/toggle_scheduler', methods=['POST'])
def toggle_scheduler():
    """Toggle scheduler state"""
    try:
        if scheduler.is_running:
            success = scheduler.stop()
            message = 'Планировщик остановлен' if success else 'Не удалось остановить планировщик'
            status = 'success' if success else 'danger'
        else:
            success = scheduler.start()
            message = 'Планировщик запущен' if success else 'Не удалось запустить планировщик'
            status = 'success' if success else 'danger'

        flash(message, status)
    except Exception as e:
        logger.error(f"Error toggling scheduler: {e}")
        flash(f'Ошибка при переключении планировщика: {str(e)}', 'danger')

    return redirect(url_for('index'))

@app.route('/run_scheduled_post_now', methods=['POST'])
def run_scheduled_post_now():
    """Run a scheduled post immediately"""
    try:
        success = scheduler.run_job_now()

        if success:
            flash('Запланированный пост успешно запущен вручную', 'success')
        else:
            flash('Не удалось запустить запланированный пост вручную', 'danger')

    except Exception as e:
        logger.error(f"Error running scheduled post: {e}")
        flash(f'Ошибка при запуске поста: {str(e)}', 'danger')

    return redirect(url_for('index'))

@app.route('/delete_topic/<path:topic>', methods=['POST'])
def delete_topic(topic):
    """Delete a custom topic"""
    try:
        custom_topics = []
        # Load all current topics
        if os.path.exists('custom_topics.txt'):
            with open('custom_topics.txt', 'r', encoding='utf-8') as f:
                custom_topics = [line.strip() for line in f.readlines() if line.strip()]

        # Remove selected topic
        if topic in custom_topics:
            custom_topics.remove(topic)

            # Rewrite file without the deleted topic
            with open('custom_topics.txt', 'w', encoding='utf-8') as f:
                for t in custom_topics:
                    f.write(f"{t}\n")

            flash(f'Тема "{topic}" удалена из избранного', 'success')

            # Update topics list in memory
            if topic in TRADING_TOPICS:
                TRADING_TOPICS.remove(topic)
        else:
            flash('Тема не найдена', 'warning')

    except Exception as e:
        logger.error(f"Error deleting topic: {e}")
        flash(f'Ошибка при удалении темы: {str(e)}', 'danger')

    return redirect(url_for('index'))

@app.route('/analytics')
def analytics():
    """Analytics dashboard"""
    # Get post history
    recent_posts = get_post_history(limit=100)
    
    # Generate analytics data
    analytics_data = generate_analytics_data(recent_posts)
    
    # Add more detailed analytics
    month_names = list(calendar.month_name)[1:]
    post_counts_by_month = [random.randint(15, 45) for _ in range(12)]
    
    # Engagement metrics (sample data)
    engagement_data = {
        'views': [random.randint(100, 500) for _ in range(7)],
        'reactions': [random.randint(10, 50) for _ in range(7)],
        'shares': [random.randint(5, 25) for _ in range(7)],
        'comments': [random.randint(3, 15) for _ in range(7)],
        'days': [(datetime.datetime.now() - datetime.timedelta(days=i)).strftime('%d.%m') for i in range(6, -1, -1)]
    }
    
    return render_template(
        'analytics.html',
        analytics_data=analytics_data,
        month_names=month_names,
        post_counts_by_month=post_counts_by_month,
        engagement_data=engagement_data,
        current_time=get_current_time_formatted(),
        current_date=get_current_date_formatted()
    )

@app.route('/manage_images', methods=['GET', 'POST'])
def manage_images():
    """Manage image URL list"""
    image_urls = []
    error_message = None
    success_message = None

    # Load existing images
    try:
        if os.path.exists('image_urls.txt'):
            with open('image_urls.txt', 'r', encoding='utf-8') as f:
                image_urls = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        logger.error(f"Error loading image URLs: {e}")
        error_message = f"Ошибка загрузки URL-ов изображений: {str(e)}"

    # Handle POST request (add/delete URL)
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            new_url = request.form.get('image_url', '').strip()
            if not new_url:
                error_message = "URL изображения не может быть пустым"
            elif not new_url.startswith(('http://', 'https://')):
                error_message = "URL должен начинаться с http:// или https://"
            elif new_url in image_urls:
                error_message = "Этот URL уже есть в списке"
            else:
                try:
                    # Check if URL is a valid image
                    response = requests.head(new_url, timeout=5)
                    content_type = response.headers.get('Content-Type', '')

                    if 'image' in content_type or any(ext in new_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        # Add URL to file
                        with open('image_urls.txt', 'a', encoding='utf-8') as f:
                            f.write(f"{new_url}\n")

                        # Update list
                        image_urls.append(new_url)
                        success_message = "URL изображения успешно добавлен"
                    else:
                        error_message = "URL не является изображением"
                except Exception as e:
                    logger.error(f"Error adding image URL: {e}")
                    error_message = f"Ошибка добавления URL: {str(e)}"

        elif action == 'delete':
            url_to_delete = request.form.get('url_to_delete')
            if url_to_delete in image_urls:
                try:
                    # Remove URL from list and rewrite file
                    image_urls.remove(url_to_delete)
                    with open('image_urls.txt', 'w', encoding='utf-8') as f:
                        for url in image_urls:
                            f.write(f"{url}\n")
                    success_message = "URL изображения успешно удален"
                except Exception as e:
                    logger.error(f"Error deleting image URL: {e}")
                    error_message = f"Ошибка удаления URL: {str(e)}"
            else:
                error_message = "URL не найден в списке"

    return render_template(
        'manage_images.html',
        image_urls=image_urls,
        error_message=error_message,
        success_message=success_message,
        current_time=get_current_time_formatted()
    )

@app.route('/api/scheduled_posts', methods=['GET'])
def api_scheduled_posts():
    """API endpoint for getting scheduled posts"""
    scheduled_posts = get_scheduled_posts()
    return jsonify(scheduled_posts)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message="Страница не найдена"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error_code=500, error_message="Внутренняя ошибка сервера"), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)