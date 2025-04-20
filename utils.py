import logging
import os
import pytz
import datetime
import json
import traceback

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Timezone settings
TIMEZONE = pytz.timezone('Asia/Dushanbe')

def format_error_for_display(error):
    """Format an exception for logging and display"""
    if hasattr(error, 'response') and hasattr(error.response, 'text'):
        try:
            # Try to parse as JSON for more detailed error info
            response_data = json.loads(error.response.text)
            return f"{error.__class__.__name__}: {response_data.get('error', {}).get('message', str(error))}"
        except (json.JSONDecodeError, AttributeError):
            # If not JSON or no 'error' key, return the raw response text
            return f"{error.__class__.__name__}: {error.response.text[:200]}"
    else:
        # For other exceptions, return the error message
        return f"{error.__class__.__name__}: {str(error)}"

def get_current_time_formatted():
    """Get current time formatted for display"""
    return datetime.datetime.now(TIMEZONE).strftime('%H:%M:%S')

def get_current_date_formatted():
    """Get current date formatted for display"""
    return datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d')

def format_time_for_schedule(time_str):
    """Format time string for schedule display"""
    try:
        hour, minute = map(int, time_str.split(':'))
        now = datetime.datetime.now(TIMEZONE)
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the time has already passed today, show it for tomorrow
        if scheduled_time < now:
            scheduled_time += datetime.timedelta(days=1)
            
        # Format with day info if it's tomorrow
        if scheduled_time.date() > now.date():
            return f"{time_str} (завтра)"
        else:
            return time_str
    except Exception as e:
        logger.error(f"Error formatting time: {e}")
        return time_str

def check_environment_variables():
    """Check required environment variables and return status"""
    required_vars = {
        'TELEGRAM_TOKEN': os.environ.get('TELEGRAM_TOKEN'),
        'CHANNEL_ID': os.environ.get('CHANNEL_ID'),
        'OPENROUTER_API_KEY': os.environ.get('OPENROUTER_API_KEY')
    }
    
    status = {
        'all_present': all(required_vars.values()),
        'details': {k: bool(v) for k, v in required_vars.items()}
    }
    
    return status

def get_system_status():
    """Get overall system status"""
    env_status = check_environment_variables()
    
    return {
        'env_variables': env_status,
        'timestamp': datetime.datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'),
        'timezone': TIMEZONE.zone
    }