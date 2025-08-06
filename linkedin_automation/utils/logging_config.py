import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(app):
    """Setup logging configuration"""
    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Setup file handler with rotation
        file_handler = RotatingFileHandler(
            'logs/linkedin_automation.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s'
        ))
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('LinkedIn Automation System startup')

def log_bot_activity(bot_type, account_email, message, level='info'):
    """Log bot activity with structured format"""
    logger = logging.getLogger('bot_activity')
    log_message = f"[{bot_type}] [{account_email}] {message}"
    
    if level == 'info':
        logger.info(log_message)
    elif level == 'warning':
        logger.warning(log_message)
    elif level == 'error':
        logger.error(log_message)
    elif level == 'debug':
        logger.debug(log_message)

def log_security_event(event_type, user_id, details):
    """Log security-related events"""
    logger = logging.getLogger('security')
    log_message = f"SECURITY: [{event_type}] User {user_id}: {details}"
    logger.warning(log_message)