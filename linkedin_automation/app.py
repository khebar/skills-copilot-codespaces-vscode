from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_migrate import Migrate
import os
import logging
from datetime import datetime

from config import config
from models import db, User, LinkedInAccount, Profile, BotRun
from scheduler import scheduler_bp, init_scheduler
from admin import admin_bp
from api import api_bp
from utils.logging_config import setup_logging

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Setup logging
    setup_logging(app)
    
    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'برای دسترسی به این صفحه باید وارد شوید.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(scheduler_bp, url_prefix='/scheduler')
    
    # Initialize scheduler
    init_scheduler(app)
    
    # Main routes
    @app.route('/')
    def index():
        """صفحه اصلی"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """داشبورد کاربر"""
        # Get user's LinkedIn accounts
        accounts = LinkedInAccount.query.filter_by(
            user_id=current_user.id, 
            is_active=True
        ).all()
        
        # Get recent bot runs
        recent_runs = BotRun.query.join(LinkedInAccount).filter(
            LinkedInAccount.user_id == current_user.id
        ).order_by(BotRun.start_time.desc()).limit(10).all()
        
        # Statistics
        stats = {
            'total_accounts': len(accounts),
            'active_runs': BotRun.query.join(LinkedInAccount).filter(
                LinkedInAccount.user_id == current_user.id,
                BotRun.status == 'running'
            ).count(),
            'successful_runs_today': BotRun.query.join(LinkedInAccount).filter(
                LinkedInAccount.user_id == current_user.id,
                BotRun.status == 'completed',
                BotRun.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            ).count(),
            'failed_runs_today': BotRun.query.join(LinkedInAccount).filter(
                LinkedInAccount.user_id == current_user.id,
                BotRun.status == 'failed',
                BotRun.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            ).count()
        }
        
        return render_template('dashboard.html', 
                             accounts=accounts, 
                             recent_runs=recent_runs,
                             stats=stats)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """صفحه ورود"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password) and user.is_active:
                login_user(user, remember=True)
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('نام کاربری یا رمز عبور اشتباه است.', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """خروج کاربر"""
        logout_user()
        flash('با موفقیت خارج شدید.', 'success')
        return redirect(url_for('index'))
    
    @app.route('/accounts')
    @login_required
    def accounts():
        """مدیریت اکانت‌های لینکدین"""
        accounts = LinkedInAccount.query.filter_by(
            user_id=current_user.id
        ).all()
        return render_template('accounts.html', accounts=accounts)
    
    @app.route('/accounts/add', methods=['GET', 'POST'])
    @login_required
    def add_account():
        """افزودن اکانت لینکدین جدید"""
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            profile_name = request.form.get('profile_name')
            
            # Check if account already exists
            existing_account = LinkedInAccount.query.filter_by(email=email).first()
            if existing_account:
                flash('این اکانت قبلاً ثبت شده است.', 'error')
                return render_template('add_account.html')
            
            # Create new account
            account = LinkedInAccount(
                user_id=current_user.id,
                email=email,
                password=password,  # Should be encrypted in production
                profile_name=profile_name
            )
            
            db.session.add(account)
            db.session.commit()
            
            flash('اکانت با موفقیت اضافه شد.', 'success')
            return redirect(url_for('accounts'))
        
        return render_template('add_account.html')
    
    @app.route('/reports')
    @login_required
    def reports():
        """گزارشات و آمار"""
        # Get user's accounts for filtering
        accounts = LinkedInAccount.query.filter_by(
            user_id=current_user.id
        ).all()
        
        # Get bot runs data
        runs_data = []
        for account in accounts:
            runs = BotRun.query.filter_by(
                linkedin_account_id=account.id
            ).order_by(BotRun.start_time.desc()).limit(50).all()
            
            for run in runs:
                runs_data.append({
                    'account_email': account.email,
                    'bot_type': run.bot_type,
                    'status': run.status,
                    'start_time': run.start_time,
                    'end_time': run.end_time,
                    'results': run.get_results()
                })
        
        return render_template('reports.html', runs_data=runs_data, accounts=accounts)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    return app

# Create application instance
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create database tables
        db.create_all()
        
        # Create admin user if doesn't exist
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@linkedin-automation.com',
                full_name='مدیر سیستم',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin/admin123")
    
    app.run(host='0.0.0.0', port=5000, debug=True)