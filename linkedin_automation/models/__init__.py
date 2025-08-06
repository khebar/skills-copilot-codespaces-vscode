from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """مشتریان سیستم"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    linkedin_accounts = db.relationship('LinkedInAccount', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class LinkedInAccount(db.Model):
    """اکانت‌های لینکدین هر مشتری"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Encrypted
    profile_name = db.Column(db.String(255))
    profile_url = db.Column(db.String(500))
    cookies = db.Column(db.Text)  # JSON string of cookies
    csrf_token = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    last_activity = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    keywords = db.relationship('Keyword', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    blacklist = db.relationship('Blacklist', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    connections = db.relationship('Connection', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    sent_invitations = db.relationship('SentInvitation', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    received_invitations = db.relationship('ReceivedInvitation', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    bot_runs = db.relationship('BotRun', backref='linkedin_account', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_cookies(self, cookies_dict):
        self.cookies = json.dumps(cookies_dict)
    
    def get_cookies(self):
        if self.cookies:
            return json.loads(self.cookies)
        return {}
    
    def __repr__(self):
        return f'<LinkedInAccount {self.email}>'

class Profile(db.Model):
    """پروفایل‌های استخراج شده"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_profile_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    headline = db.Column(db.Text)
    location = db.Column(db.String(255))
    profile_url = db.Column(db.String(500))
    avatar_url = db.Column(db.String(500))
    follower_count = db.Column(db.Integer)
    connection_count = db.Column(db.Integer)
    is_premium = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Profile {self.name}>'

class Connection(db.Model):
    """کانکشن‌ها"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    connected_at = db.Column(db.DateTime)
    source = db.Column(db.String(100))  # How the connection was made
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    profile = db.relationship('Profile', backref='connections')
    
    def __repr__(self):
        return f'<Connection {self.id}>'

class SentInvitation(db.Model):
    """دعوتنامه‌های ارسالی"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default='sent')  # sent, accepted, declined, withdrawn
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    
    profile = db.relationship('Profile', backref='sent_invitations')
    
    def __repr__(self):
        return f'<SentInvitation {self.id}>'

class ReceivedInvitation(db.Model):
    """دعوتنامه‌های دریافتی"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default='received')  # received, accepted, declined
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    
    profile = db.relationship('Profile', backref='received_invitations')
    
    def __repr__(self):
        return f'<ReceivedInvitation {self.id}>'

class Keyword(db.Model):
    """کلمات کلیدی هر اکانت"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    keyword = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Keyword {self.keyword}>'

class Blacklist(db.Model):
    """کلمات بلک‌لیست هر اکانت"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    keyword = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Blacklist {self.keyword}>'

class Post(db.Model):
    """پست‌های پردازش شده"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    linkedin_post_id = db.Column(db.String(255), unique=True, nullable=False)
    author_profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'))
    content = db.Column(db.Text)
    post_url = db.Column(db.String(500))
    likes_count = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    reposts_count = db.Column(db.Integer, default=0)
    posted_at = db.Column(db.DateTime)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('Profile', backref='posts')
    
    def __repr__(self):
        return f'<Post {self.linkedin_post_id}>'

class Comment(db.Model):
    """کامنت‌های ارسالی"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    linkedin_comment_id = db.Column(db.String(255))
    status = db.Column(db.String(50), default='sent')  # sent, failed
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', backref='comments')
    
    def __repr__(self):
        return f'<Comment {self.id}>'

class BotRun(db.Model):
    """تاریخچه اجرای رباتها"""
    id = db.Column(db.Integer, primary_key=True)
    linkedin_account_id = db.Column(db.Integer, db.ForeignKey('linked_in_account.id'), nullable=False)
    bot_type = db.Column(db.String(100), nullable=False)  # activity, connection_request, connection_scraper, etc.
    status = db.Column(db.String(50), nullable=False)  # running, completed, failed, stopped
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    results = db.Column(db.Text)  # JSON string of results
    error_message = db.Column(db.Text)
    
    def set_results(self, results_dict):
        self.results = json.dumps(results_dict)
    
    def get_results(self):
        if self.results:
            return json.loads(self.results)
        return {}
    
    def __repr__(self):
        return f'<BotRun {self.bot_type}>'