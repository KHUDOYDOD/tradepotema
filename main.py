import os
import logging
import datetime
import random
import requests
import importlib
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from jinja2 import Environment
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

# Constants
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@tradepotrest')
SCHEDULE_TIMES = ["10:30", "13:30", "15:00", "17:00", "18:30"]

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

    # Add statistics
    stats = {
        'total_posts': 0,
        'successful_posts': 0,
        'failed_posts': 0,
        'topics_count': len(TRADING_TOPICS) + len(custom_topics),
        'images_count': 0,
        'today_posts': 0
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
        stats=stats
    )

@app.route('/create_post', methods=['POST'])
def create_post():
    """Create and send a post"""
    theme = request.form.get('theme', '').strip()
    save_theme = request.form.get('save_theme') == 'on'

    if not theme:
        flash('Пожалуйста, укажите тему поста', 'warning')
        return redirect(url_for('index'))

    try:
        # Create and send the post
        success, text, image_url, result = create_and_send_post(theme)

        if success:
            flash(f'Пост на тему "{theme}" успешно отправлен в канал {CHANNEL_ID}.', 'success')

            # Save the theme if user checked the box and it's not already in the list
            if save_theme and theme not in TRADING_TOPICS:
                try:
                    # Create file for storing custom topics if it doesn't exist
                    custom_topics_file = 'custom_topics.txt'

                    # Create or append to file
                    with open(custom_topics_file, 'a', encoding='utf-8') as f:
                        f.write(f"{theme}\n")

                    flash(f'Тема "{theme}" сохранена в избранное', 'success')

                    # Add topic to current topics list
                    TRADING_TOPICS.append(theme)
                except Exception as save_err:
                    logger.error(f"Error saving custom theme: {save_err}")
        else:
            flash(f'Ошибка при отправке поста: {result}', 'danger')

    except Exception as e:
        logger.error(f"Error in create_post route: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')

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

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, error_message="Страница не найдена"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error_code=500, error_message="Внутренняя ошибка сервера"), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)