import datetime
from app import db

class Post(db.Model):
    """Model for storing Telegram posts"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    theme = db.Column(db.String(200), nullable=True)
    text_snippet = db.Column(db.String(500), nullable=True)
    full_text = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    success = db.Column(db.Boolean, default=False)
    message_id = db.Column(db.String(100), nullable=True)
    error = db.Column(db.Text, nullable=True)
    processing_time = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f"<Post {self.id}: {self.theme}>"
    
    def to_dict(self):
        """Convert post to dictionary for API/JSON responses"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'theme': self.theme,
            'text_snippet': self.text_snippet,
            'full_text': self.full_text,
            'image_url': self.image_url,
            'success': self.success,
            'message_id': self.message_id,
            'error': self.error,
            'processing_time': self.processing_time
        }