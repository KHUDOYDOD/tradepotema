import os
import logging
import datetime
import threading
import time
import pytz
import random
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bot import create_and_send_post, get_random_topic, TRADING_TOPICS

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TIMEZONE = pytz.timezone('Asia/Dushanbe')
DEFAULT_SCHEDULE_TIMES = ["10:30", "13:30", "15:00", "17:00", "18:30"]

class PostScheduler:
    def __init__(self, timezone=TIMEZONE, schedule_times=None):
        self.timezone = timezone
        self.schedule_times = schedule_times or DEFAULT_SCHEDULE_TIMES
        self.scheduler = None
        self.jobs = []
        self.is_running = False
        self.lock = threading.Lock()
        self.used_topics = []
        self.max_topic_history = 10
        
    def _format_log_time(self):
        """Format current time for logging"""
        return datetime.datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        
    def _scheduled_post_task(self):
        """Task to be executed by the scheduler"""
        try:
            logger.info(f"[{self._format_log_time()}] Starting scheduled post creation")
            
            # Get a random topic that wasn't used recently
            available_topics = [t for t in TRADING_TOPICS if t not in self.used_topics]
            if not available_topics:
                # If all topics were used, reset history
                self.used_topics = []
                available_topics = TRADING_TOPICS
            
            topic = random.choice(available_topics)
            self.used_topics.append(topic)
            
            # Keep only recent history
            if len(self.used_topics) > self.max_topic_history:
                self.used_topics.pop(0)
                
            logger.info(f"Selected topic: {topic} (used topics: {len(self.used_topics)})")
            
            # Create and send the post
            success, text, image_url, result = create_and_send_post(topic)
            
            if success:
                logger.info(f"[{self._format_log_time()}] Scheduled post created and sent successfully")
            else:
                logger.error(f"[{self._format_log_time()}] Scheduled post creation failed: {result}")
                
            return success
        except Exception as e:
            logger.error(f"Error in scheduled post task: {e}")
            return False
    
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return False
            
        try:
            logger.info(f"[{self._format_log_time()}] Starting scheduler with timezone: {self.timezone.zone}")
            
            # Create scheduler
            self.scheduler = BackgroundScheduler(timezone=self.timezone)
            
            # Add jobs for each scheduled time
            self.jobs = []
            for time_str in self.schedule_times:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    job = self.scheduler.add_job(
                        self._scheduled_post_task,
                        CronTrigger(hour=hour, minute=minute),
                        name=f"Post at {time_str}",
                        misfire_grace_time=3600  # Allow job to be executed up to 1 hour late
                    )
                    self.jobs.append(job)
                    logger.info(f"Added job for {time_str}")
                except Exception as e:
                    logger.error(f"Failed to add job for time {time_str}: {e}")
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            logger.info(f"[{self._format_log_time()}] Scheduler started with {len(self.jobs)} jobs")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            return False
            
    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return False
            
        try:
            logger.info(f"[{self._format_log_time()}] Stopping scheduler")
            if self.scheduler:
                self.scheduler.shutdown()
            self.is_running = False
            self.jobs = []
            logger.info(f"[{self._format_log_time()}] Scheduler stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return False
            
    def get_next_run_times(self):
        """Get the next run times for all jobs"""
        if not self.is_running or not self.scheduler:
            return []
            
        next_runs = []
        now = datetime.datetime.now(self.timezone)
        
        for job in self.jobs:
            next_run = job.next_run_time
            if next_run:
                time_diff = next_run - now
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                next_runs.append({
                    'job_name': job.name,
                    'next_run_time': next_run.strftime('%Y-%m-%d %H:%M:%S'),
                    'relative_time': f"{hours}ч {minutes}м" if time_diff.days == 0 else f"{time_diff.days}д {hours}ч {minutes}м"
                })
                
        return sorted(next_runs, key=lambda x: x['next_run_time'])
        
    def get_status(self):
        """Get the scheduler status"""
        return {
            'is_running': self.is_running,
            'job_count': len(self.jobs) if self.is_running else 0,
            'schedule_times': self.schedule_times,
            'timezone': self.timezone.zone,
            'next_runs': self.get_next_run_times()
        }
        
    def run_job_now(self):
        """Run a job immediately"""
        try:
            logger.info(f"[{self._format_log_time()}] Running job manually")
            
            # Get random topic
            topic = get_random_topic()
            logger.info(f"Selected topic: {topic}")
            
            # Create and send post (without using locks)
            success, text, image_url, result = create_and_send_post(topic)
            
            if success:
                logger.info(f"[{self._format_log_time()}] Manual post created and sent successfully")
            else:
                logger.error(f"[{self._format_log_time()}] Manual post creation failed: {result}")
                
            return success
        except Exception as e:
            logger.error(f"Error in manual job execution: {e}")
            return False

# Create global scheduler instance
scheduler = PostScheduler()