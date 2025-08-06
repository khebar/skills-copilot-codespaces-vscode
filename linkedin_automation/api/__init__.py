from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from models import db, User, LinkedInAccount, Profile, BotRun, Connection, SentInvitation, ReceivedInvitation, Keyword, Blacklist
from utils.logging_config import log_security_event

api_bp = Blueprint('api', __name__)

# Helper function for pagination
def paginate_query(query, page, per_page=20):
    """Helper function to paginate queries"""
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return {
        'items': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in pagination.items],
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': pagination.per_page,
        'total': pagination.total,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    }

# User Management API
@api_bp.route('/users', methods=['GET'])
@login_required
def api_get_users():
    """Get list of users (admin only)"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    page = request.args.get('page', 1, type=int)
    query = User.query.order_by(User.created_at.desc())
    
    result = paginate_query(query, page)
    
    # Convert user objects to dict
    result['items'] = []
    for user in query.paginate(page=page, per_page=20, error_out=False).items:
        result['items'].append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'created_at': user.created_at.isoformat(),
            'updated_at': user.updated_at.isoformat()
        })
    
    return jsonify(result)

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
def api_get_user(user_id):
    """Get specific user details"""
    if not current_user.is_admin and current_user.id != user_id:
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': user.full_name,
        'is_active': user.is_active,
        'is_admin': user.is_admin,
        'created_at': user.created_at.isoformat(),
        'updated_at': user.updated_at.isoformat(),
        'linkedin_accounts_count': user.linkedin_accounts.count()
    })

# LinkedIn Accounts API
@api_bp.route('/accounts', methods=['GET'])
@login_required
def api_get_accounts():
    """Get LinkedIn accounts"""
    page = request.args.get('page', 1, type=int)
    
    if current_user.is_admin:
        query = LinkedInAccount.query
    else:
        query = LinkedInAccount.query.filter_by(user_id=current_user.id)
    
    accounts = query.order_by(LinkedInAccount.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    result = {
        'items': [],
        'page': accounts.page,
        'pages': accounts.pages,
        'per_page': accounts.per_page,
        'total': accounts.total,
        'has_next': accounts.has_next,
        'has_prev': accounts.has_prev
    }
    
    for account in accounts.items:
        result['items'].append({
            'id': account.id,
            'user_id': account.user_id,
            'user_name': account.user.full_name,
            'email': account.email,
            'profile_name': account.profile_name,
            'profile_url': account.profile_url,
            'is_active': account.is_active,
            'last_activity': account.last_activity.isoformat() if account.last_activity else None,
            'created_at': account.created_at.isoformat(),
            'keywords_count': account.keywords.count(),
            'blacklist_count': account.blacklist.count()
        })
    
    return jsonify(result)

@api_bp.route('/accounts/<int:account_id>', methods=['GET'])
@login_required
def api_get_account(account_id):
    """Get specific account details"""
    account = LinkedInAccount.query.get_or_404(account_id)
    
    # Check access rights
    if not current_user.is_admin and account.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'id': account.id,
        'user_id': account.user_id,
        'user_name': account.user.full_name,
        'email': account.email,
        'profile_name': account.profile_name,
        'profile_url': account.profile_url,
        'is_active': account.is_active,
        'last_activity': account.last_activity.isoformat() if account.last_activity else None,
        'created_at': account.created_at.isoformat(),
        'updated_at': account.updated_at.isoformat(),
        'keywords': [{'id': k.id, 'keyword': k.keyword, 'is_active': k.is_active} 
                    for k in account.keywords],
        'blacklist': [{'id': b.id, 'keyword': b.keyword, 'is_active': b.is_active} 
                     for b in account.blacklist]
    })

@api_bp.route('/accounts/<int:account_id>/keywords', methods=['GET', 'POST'])
@login_required
def api_account_keywords(account_id):
    """Manage account keywords"""
    account = LinkedInAccount.query.get_or_404(account_id)
    
    # Check access rights
    if not current_user.is_admin and account.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    if request.method == 'GET':
        keywords = Keyword.query.filter_by(linkedin_account_id=account_id).all()
        return jsonify({
            'keywords': [{'id': k.id, 'keyword': k.keyword, 'is_active': k.is_active, 
                         'created_at': k.created_at.isoformat()} for k in keywords]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        keyword_text = data.get('keyword', '').strip()
        
        if not keyword_text:
            return jsonify({'error': 'Keyword cannot be empty'}), 400
        
        # Check if keyword already exists
        existing = Keyword.query.filter_by(
            linkedin_account_id=account_id,
            keyword=keyword_text
        ).first()
        
        if existing:
            return jsonify({'error': 'Keyword already exists'}), 400
        
        # Create new keyword
        keyword = Keyword(
            linkedin_account_id=account_id,
            keyword=keyword_text
        )
        db.session.add(keyword)
        db.session.commit()
        
        return jsonify({
            'id': keyword.id,
            'keyword': keyword.keyword,
            'is_active': keyword.is_active,
            'created_at': keyword.created_at.isoformat()
        }), 201

@api_bp.route('/accounts/<int:account_id>/blacklist', methods=['GET', 'POST'])
@login_required
def api_account_blacklist(account_id):
    """Manage account blacklist"""
    account = LinkedInAccount.query.get_or_404(account_id)
    
    # Check access rights
    if not current_user.is_admin and account.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    if request.method == 'GET':
        blacklist = Blacklist.query.filter_by(linkedin_account_id=account_id).all()
        return jsonify({
            'blacklist': [{'id': b.id, 'keyword': b.keyword, 'is_active': b.is_active,
                          'created_at': b.created_at.isoformat()} for b in blacklist]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        keyword_text = data.get('keyword', '').strip()
        
        if not keyword_text:
            return jsonify({'error': 'Blacklist keyword cannot be empty'}), 400
        
        # Check if keyword already exists
        existing = Blacklist.query.filter_by(
            linkedin_account_id=account_id,
            keyword=keyword_text
        ).first()
        
        if existing:
            return jsonify({'error': 'Blacklist keyword already exists'}), 400
        
        # Create new blacklist entry
        blacklist_entry = Blacklist(
            linkedin_account_id=account_id,
            keyword=keyword_text
        )
        db.session.add(blacklist_entry)
        db.session.commit()
        
        return jsonify({
            'id': blacklist_entry.id,
            'keyword': blacklist_entry.keyword,
            'is_active': blacklist_entry.is_active,
            'created_at': blacklist_entry.created_at.isoformat()
        }), 201

# Bot Runs API
@api_bp.route('/bot_runs', methods=['GET'])
@login_required
def api_get_bot_runs():
    """Get bot runs"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    bot_type = request.args.get('bot_type')
    
    if current_user.is_admin:
        query = BotRun.query
    else:
        query = BotRun.query.join(LinkedInAccount).filter(
            LinkedInAccount.user_id == current_user.id
        )
    
    if status:
        query = query.filter(BotRun.status == status)
    if bot_type:
        query = query.filter(BotRun.bot_type == bot_type)
    
    bot_runs = query.order_by(BotRun.start_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    result = {
        'items': [],
        'page': bot_runs.page,
        'pages': bot_runs.pages,
        'per_page': bot_runs.per_page,
        'total': bot_runs.total,
        'has_next': bot_runs.has_next,
        'has_prev': bot_runs.has_prev
    }
    
    for run in bot_runs.items:
        duration = None
        if run.end_time:
            duration = (run.end_time - run.start_time).total_seconds()
        
        result['items'].append({
            'id': run.id,
            'account_email': run.linkedin_account.email,
            'bot_type': run.bot_type,
            'status': run.status,
            'start_time': run.start_time.isoformat(),
            'end_time': run.end_time.isoformat() if run.end_time else None,
            'duration_seconds': duration,
            'results': run.get_results(),
            'error_message': run.error_message
        })
    
    return jsonify(result)

@api_bp.route('/bot_runs/<int:run_id>', methods=['GET'])
@login_required
def api_get_bot_run(run_id):
    """Get specific bot run details"""
    bot_run = BotRun.query.get_or_404(run_id)
    
    # Check access rights
    if not current_user.is_admin and bot_run.linkedin_account.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    duration = None
    if bot_run.end_time:
        duration = (bot_run.end_time - bot_run.start_time).total_seconds()
    
    return jsonify({
        'id': bot_run.id,
        'account_email': bot_run.linkedin_account.email,
        'account_id': bot_run.linkedin_account_id,
        'bot_type': bot_run.bot_type,
        'status': bot_run.status,
        'start_time': bot_run.start_time.isoformat(),
        'end_time': bot_run.end_time.isoformat() if bot_run.end_time else None,
        'duration_seconds': duration,
        'results': bot_run.get_results(),
        'error_message': bot_run.error_message
    })

# Statistics API
@api_bp.route('/statistics/overview', methods=['GET'])
@login_required
def api_statistics_overview():
    """Get system statistics overview"""
    if current_user.is_admin:
        # Admin sees all data
        stats = {
            'total_users': User.query.count(),
            'total_accounts': LinkedInAccount.query.count(),
            'active_accounts': LinkedInAccount.query.filter_by(is_active=True).count(),
            'total_profiles': Profile.query.count(),
            'total_connections': Connection.query.count(),
            'total_sent_invitations': SentInvitation.query.count(),
            'total_received_invitations': ReceivedInvitation.query.count(),
            'running_bots': BotRun.query.filter_by(status='running').count()
        }
    else:
        # User sees only their data
        user_accounts = LinkedInAccount.query.filter_by(user_id=current_user.id).all()
        account_ids = [acc.id for acc in user_accounts]
        
        stats = {
            'user_accounts': len(user_accounts),
            'active_accounts': sum(1 for acc in user_accounts if acc.is_active),
            'connections': Connection.query.filter(Connection.linkedin_account_id.in_(account_ids)).count(),
            'sent_invitations': SentInvitation.query.filter(SentInvitation.linkedin_account_id.in_(account_ids)).count(),
            'received_invitations': ReceivedInvitation.query.filter(ReceivedInvitation.linkedin_account_id.in_(account_ids)).count(),
            'running_bots': BotRun.query.filter(
                BotRun.linkedin_account_id.in_(account_ids),
                BotRun.status == 'running'
            ).count()
        }
    
    return jsonify(stats)

@api_bp.route('/statistics/daily', methods=['GET'])
@login_required
def api_statistics_daily():
    """Get daily statistics"""
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    if current_user.is_admin:
        query = BotRun.query
    else:
        user_account_ids = [acc.id for acc in LinkedInAccount.query.filter_by(user_id=current_user.id)]
        query = BotRun.query.filter(BotRun.linkedin_account_id.in_(user_account_ids))
    
    daily_stats = query.filter(
        BotRun.start_time >= start_date
    ).with_entities(
        db.func.date(BotRun.start_time).label('date'),
        db.func.count(BotRun.id).label('total_runs'),
        db.func.count(db.case([(BotRun.status == 'completed', 1)])).label('successful_runs'),
        db.func.count(db.case([(BotRun.status == 'failed', 1)])).label('failed_runs')
    ).group_by(
        db.func.date(BotRun.start_time)
    ).all()
    
    result = []
    for stat in daily_stats:
        result.append({
            'date': stat.date.isoformat(),
            'total_runs': stat.total_runs,
            'successful_runs': stat.successful_runs,
            'failed_runs': stat.failed_runs,
            'success_rate': (stat.successful_runs / stat.total_runs * 100) if stat.total_runs > 0 else 0
        })
    
    return jsonify({'daily_stats': result})

# Security endpoint for logging
@api_bp.route('/security/log', methods=['POST'])
@login_required
def api_log_security_event():
    """Log security events"""
    data = request.get_json()
    event_type = data.get('event_type', 'unknown')
    details = data.get('details', '')
    
    log_security_event(event_type, current_user.id, details)
    
    return jsonify({'success': True, 'message': 'Security event logged'})

# Health check endpoint
@api_bp.route('/health', methods=['GET'])
def api_health_check():
    """API health check"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'disconnected',
            'error': str(e)
        }), 500