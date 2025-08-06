import os
from datetime import timedelta

class Config:
    # Basic Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'linkedin-automation-secret-key-2023'
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///linkedin_automation.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Bot Configuration
    BOT_DELAY_MIN = int(os.environ.get('BOT_DELAY_MIN', '2'))
    BOT_DELAY_MAX = int(os.environ.get('BOT_DELAY_MAX', '5'))
    
    # Activity Bot Limits
    ACTIVITY_BOT_MAX_HOURS = int(os.environ.get('ACTIVITY_BOT_MAX_HOURS', '7'))
    
    # Connection Request Bot Limits
    CONNECTION_REQUEST_LIMIT = int(os.environ.get('CONNECTION_REQUEST_LIMIT', '28'))
    
    # Scheduler Configuration
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Asia/Tehran'
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE_PATH = os.environ.get('LOG_FILE_PATH', 'logs/linkedin_automation.log')
    
    # Security Configuration
    CSRF_TIME_LIMIT = timedelta(hours=1)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # LinkedIn Configuration
    LINKEDIN_BASE_URL = 'https://www.linkedin.com'
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}