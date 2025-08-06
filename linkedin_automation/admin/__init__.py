from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

from models import db, User, LinkedInAccount, Profile, BotRun, Connection, SentInvitation, ReceivedInvitation

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
def require_admin():
    """Ensure all admin routes require admin access"""
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for('login'))

@admin_bp.route('/')
@login_required
def admin_dashboard():
    """Admin dashboard with system overview"""
    # Get system statistics
    stats = {
        'total_users': User.query.count(),
        'total_accounts': LinkedInAccount.query.count(),
        'active_accounts': LinkedInAccount.query.filter_by(is_active=True).count(),
        'total_profiles': Profile.query.count(),
        'total_connections': Connection.query.count(),
        'total_sent_invitations': SentInvitation.query.count(),
        'total_received_invitations': ReceivedInvitation.query.count(),
        'running_bots': BotRun.query.filter_by(status='running').count(),
        'failed_runs_today': BotRun.query.filter(
            BotRun.status == 'failed',
            BotRun.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
    }
    
    # Get recent activities
    recent_runs = BotRun.query.order_by(BotRun.start_time.desc()).limit(20).all()
    
    # Get top performing accounts
    top_accounts = db.session.query(
        LinkedInAccount,
        db.func.count(BotRun.id).label('total_runs'),
        db.func.count(db.case((BotRun.status == 'completed', 1))).label('successful_runs')
    ).join(BotRun).group_by(LinkedInAccount.id).order_by(
        db.text('successful_runs DESC')
    ).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_runs=recent_runs,
                         top_accounts=top_accounts)

@admin_bp.route('/users')
@login_required
def manage_users():
    """Manage system users"""
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    """Create new user"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        is_admin = bool(request.form.get('is_admin'))
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('نام کاربری قبلاً استفاده شده است.', 'error')
            return render_template('admin/create_user.html')
        
        if User.query.filter_by(email=email).first():
            flash('ایمیل قبلاً استفاده شده است.', 'error')
            return render_template('admin/create_user.html')
        
        # Create user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            is_admin=is_admin
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('کاربر با موفقیت ایجاد شد.', 'success')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/create_user.html')

@admin_bp.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'فعال' if user.is_active else 'غیرفعال'
    return jsonify({'success': True, 'message': f'کاربر {status} شد.', 'is_active': user.is_active})

@admin_bp.route('/accounts')
@login_required
def manage_accounts():
    """Manage LinkedIn accounts"""
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', type=int)
    
    query = LinkedInAccount.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    accounts = query.paginate(
        page=page, per_page=20, error_out=False
    )
    
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('admin/accounts.html', accounts=accounts, users=users)

@admin_bp.route('/accounts/<int:account_id>/toggle_active', methods=['POST'])
@login_required
def toggle_account_active(account_id):
    """Toggle account active status"""
    account = LinkedInAccount.query.get_or_404(account_id)
    account.is_active = not account.is_active
    account.updated_at = datetime.utcnow()
    db.session.commit()
    
    status = 'فعال' if account.is_active else 'غیرفعال'
    return jsonify({'success': True, 'message': f'اکانت {status} شد.', 'is_active': account.is_active})

@admin_bp.route('/bot_runs')
@login_required
def manage_bot_runs():
    """Manage bot runs"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    bot_type = request.args.get('bot_type')
    account_id = request.args.get('account_id', type=int)
    
    query = BotRun.query
    
    if status:
        query = query.filter_by(status=status)
    if bot_type:
        query = query.filter_by(bot_type=bot_type)
    if account_id:
        query = query.filter_by(linkedin_account_id=account_id)
    
    bot_runs = query.order_by(BotRun.start_time.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get filter options
    accounts = LinkedInAccount.query.all()
    bot_types = ['activity_bot', 'connection_request_bot', 'connection_scraper', 
                'sent_invitations_scraper', 'received_invitations_scraper']
    statuses = ['running', 'completed', 'failed', 'stopped']
    
    return render_template('admin/bot_runs.html', 
                         bot_runs=bot_runs,
                         accounts=accounts,
                         bot_types=bot_types,
                         statuses=statuses)

@admin_bp.route('/bot_runs/<int:run_id>')
@login_required
def bot_run_detail(run_id):
    """View bot run details"""
    bot_run = BotRun.query.get_or_404(run_id)
    return render_template('admin/bot_run_detail.html', bot_run=bot_run)

@admin_bp.route('/statistics')
@login_required
def statistics():
    """System statistics and analytics"""
    # Daily statistics for the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    daily_stats = db.session.query(
        db.func.date(BotRun.start_time).label('date'),
        db.func.count(BotRun.id).label('total_runs'),
        db.func.count(db.case((BotRun.status == 'completed', 1))).label('successful_runs'),
        db.func.count(db.case((BotRun.status == 'failed', 1))).label('failed_runs')
    ).filter(
        BotRun.start_time >= thirty_days_ago
    ).group_by(
        db.func.date(BotRun.start_time)
    ).all()
    
    # Bot type performance
    bot_performance = db.session.query(
        BotRun.bot_type,
        db.func.count(BotRun.id).label('total_runs'),
        db.func.count(db.case((BotRun.status == 'completed', 1))).label('successful_runs'),
        db.func.avg(
            db.extract('epoch', BotRun.end_time - BotRun.start_time)
        ).label('avg_duration')
    ).filter(
        BotRun.start_time >= thirty_days_ago
    ).group_by(BotRun.bot_type).all()
    
    # Account performance
    account_performance = db.session.query(
        LinkedInAccount.email,
        db.func.count(BotRun.id).label('total_runs'),
        db.func.count(db.case((BotRun.status == 'completed', 1))).label('successful_runs'),
        db.func.count(db.case((BotRun.status == 'failed', 1))).label('failed_runs')
    ).join(BotRun).filter(
        BotRun.start_time >= thirty_days_ago
    ).group_by(LinkedInAccount.id).all()
    
    return render_template('admin/statistics.html',
                         daily_stats=daily_stats,
                         bot_performance=bot_performance,
                         account_performance=account_performance)

@admin_bp.route('/system_logs')
@login_required
def system_logs():
    """View system logs"""
    # This would read from log files - simplified for demo
    log_lines = []
    try:
        with open('logs/linkedin_automation.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Get last 1000 lines
            log_lines = lines[-1000:] if len(lines) > 1000 else lines
            log_lines.reverse()  # Show newest first
    except FileNotFoundError:
        log_lines = ['No log file found.']
    except Exception as e:
        log_lines = [f'Error reading log file: {str(e)}']
    
    return render_template('admin/system_logs.html', log_lines=log_lines)

@admin_bp.route('/clear_cookies/<int:account_id>', methods=['POST'])
@login_required
def clear_cookies(account_id):
    """Clear stored cookies for an account"""
    account = LinkedInAccount.query.get_or_404(account_id)
    account.cookies = None
    account.csrf_token = None
    account.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'کوکی‌ها پاک شدند.'})

@admin_bp.route('/force_stop_bot/<int:run_id>', methods=['POST'])
@login_required
def force_stop_bot(run_id):
    """Force stop a running bot"""
    bot_run = BotRun.query.get_or_404(run_id)
    
    if bot_run.status == 'running':
        bot_run.status = 'stopped'
        bot_run.end_time = datetime.utcnow()
        bot_run.error_message = 'Manually stopped by admin'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'ربات متوقف شد.'})
    else:
        return jsonify({'success': False, 'message': 'ربات در حال اجرا نیست.'})

@admin_bp.route('/export_data')
@login_required
def export_data():
    """Export system data"""
    # This would implement data export functionality
    # For now, return a simple response
    return jsonify({
        'message': 'Data export functionality would be implemented here',
        'timestamp': datetime.utcnow().isoformat()
    })