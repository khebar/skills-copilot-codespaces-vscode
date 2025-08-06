from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

from models import db, LinkedInAccount, BotRun
from bots.activity_bot import ActivityBot
from bots.connection_request_bot import ConnectionRequestBot
from bots.connection_scraper import ConnectionScraper
from bots.sent_invitations_scraper import SentInvitationsScraper
from bots.received_invitations_scraper import ReceivedInvitationsScraper
from utils.logging_config import log_bot_activity

scheduler_bp = Blueprint('scheduler', __name__)
bot_scheduler = None

def init_scheduler(app):
    """Initialize the APScheduler"""
    global bot_scheduler
    
    bot_scheduler = BackgroundScheduler()
    bot_scheduler.configure(timezone='Asia/Tehran')
    
    # Add daily job for all bots
    bot_scheduler.add_job(
        func=run_daily_automation,
        trigger=CronTrigger(hour=9, minute=0),  # 9:00 AM Tehran time
        id='daily_automation',
        name='Daily LinkedIn Automation',
        replace_existing=True
    )
    
    bot_scheduler.start()
    app.logger.info('Bot scheduler initialized and started')

def run_daily_automation():
    """Run daily automation for all active LinkedIn accounts"""
    try:
        # Get all active LinkedIn accounts
        active_accounts = LinkedInAccount.query.filter_by(is_active=True).all()
        
        for account in active_accounts:
            try:
                log_bot_activity('scheduler', account.email, "Starting daily automation")
                
                # Run Activity Bot (7 hours max)
                activity_bot = ActivityBot(account)
                activity_bot.run()
                
                # Wait a bit between bots
                import time
                time.sleep(300)  # 5 minutes
                
                # Run Connection Request Bot (28 requests max)
                connection_bot = ConnectionRequestBot(account)
                connection_bot.run()
                
                # Wait before secondary bots
                time.sleep(300)
                
                # Run secondary bots
                run_secondary_bots(account)
                
                log_bot_activity('scheduler', account.email, "Daily automation completed")
                
            except Exception as e:
                log_bot_activity('scheduler', account.email, 
                               f"Error in daily automation: {str(e)}", 'error')
                continue
    
    except Exception as e:
        logging.error(f"Error in daily automation: {str(e)}")

def run_secondary_bots(account):
    """Run secondary scraper bots"""
    try:
        # Connection Scraper
        connection_scraper = ConnectionScraper(account)
        connection_scraper.run()
        
        import time
        time.sleep(180)  # 3 minutes
        
        # Sent Invitations Scraper
        sent_scraper = SentInvitationsScraper(account)
        sent_scraper.run()
        
        time.sleep(180)
        
        # Received Invitations Scraper
        received_scraper = ReceivedInvitationsScraper(account)
        received_scraper.run()
        
    except Exception as e:
        log_bot_activity('scheduler', account.email, 
                       f"Error in secondary bots: {str(e)}", 'error')

@scheduler_bp.route('/status')
@login_required
def scheduler_status():
    """Get scheduler status"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    global bot_scheduler
    
    if bot_scheduler:
        jobs = []
        for job in bot_scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return jsonify({
            'running': bot_scheduler.running,
            'jobs': jobs
        })
    
    return jsonify({'running': False, 'jobs': []})

@scheduler_bp.route('/start', methods=['POST'])
@login_required
def start_scheduler():
    """Start the scheduler"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    global bot_scheduler
    
    try:
        if bot_scheduler and not bot_scheduler.running:
            bot_scheduler.start()
            return jsonify({'success': True, 'message': 'Scheduler started'})
        elif bot_scheduler and bot_scheduler.running:
            return jsonify({'success': False, 'message': 'Scheduler already running'})
        else:
            return jsonify({'success': False, 'message': 'Scheduler not initialized'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@scheduler_bp.route('/stop', methods=['POST'])
@login_required
def stop_scheduler():
    """Stop the scheduler"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    global bot_scheduler
    
    try:
        if bot_scheduler and bot_scheduler.running:
            bot_scheduler.shutdown()
            return jsonify({'success': True, 'message': 'Scheduler stopped'})
        else:
            return jsonify({'success': False, 'message': 'Scheduler not running'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@scheduler_bp.route('/run_now', methods=['POST'])
@login_required
def run_now():
    """Run automation immediately for selected accounts"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    account_ids = request.json.get('account_ids', [])
    bot_type = request.json.get('bot_type', 'all')
    
    if not account_ids:
        return jsonify({'success': False, 'message': 'No accounts selected'})
    
    try:
        for account_id in account_ids:
            account = LinkedInAccount.query.get(account_id)
            if not account:
                continue
            
            # Run in background
            global bot_scheduler
            if bot_scheduler:
                if bot_type == 'activity' or bot_type == 'all':
                    bot_scheduler.add_job(
                        func=lambda a=account: ActivityBot(a).run(),
                        id=f'manual_activity_{account.id}_{datetime.utcnow().timestamp()}',
                        name=f'Manual Activity Bot - {account.email}'
                    )
                
                if bot_type == 'connection' or bot_type == 'all':
                    bot_scheduler.add_job(
                        func=lambda a=account: ConnectionRequestBot(a).run(),
                        id=f'manual_connection_{account.id}_{datetime.utcnow().timestamp()}',
                        name=f'Manual Connection Bot - {account.email}'
                    )
                
                if bot_type == 'scraper' or bot_type == 'all':
                    bot_scheduler.add_job(
                        func=lambda a=account: run_secondary_bots(a),
                        id=f'manual_scraper_{account.id}_{datetime.utcnow().timestamp()}',
                        name=f'Manual Scraper Bots - {account.email}'
                    )
        
        return jsonify({'success': True, 'message': f'Started bots for {len(account_ids)} accounts'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@scheduler_bp.route('/recent_runs')
@login_required
def recent_runs():
    """Get recent bot runs"""
    if current_user.is_admin:
        # Admin can see all runs
        runs = BotRun.query.order_by(BotRun.start_time.desc()).limit(50).all()
    else:
        # Users can only see their own runs
        runs = BotRun.query.join(LinkedInAccount).filter(
            LinkedInAccount.user_id == current_user.id
        ).order_by(BotRun.start_time.desc()).limit(50).all()
    
    runs_data = []
    for run in runs:
        runs_data.append({
            'id': run.id,
            'account_email': run.linkedin_account.email,
            'bot_type': run.bot_type,
            'status': run.status,
            'start_time': run.start_time.isoformat(),
            'end_time': run.end_time.isoformat() if run.end_time else None,
            'results': run.get_results(),
            'error_message': run.error_message
        })
    
    return jsonify({'runs': runs_data})