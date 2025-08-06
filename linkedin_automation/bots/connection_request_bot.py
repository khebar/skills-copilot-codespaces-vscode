import random
import time
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.linkedin_bot_base import LinkedInBot
from utils.logging_config import log_bot_activity
from models import db, Profile, SentInvitation, BotRun, Post

class ConnectionRequestBot(LinkedInBot):
    """ربات ارسال درخواست کانکشن - ارسال درخواست کانکشن به reposter ها"""
    
    def __init__(self, account):
        super().__init__(account, 'connection_request_bot')
        self.max_connections = 28  # Maximum 28 connection requests per day
        self.start_time = None
        self.sent_requests = 0
        self.bot_run_record = None
    
    def run(self):
        """اجرای اصلی ربات درخواست کانکشن"""
        self.start_time = datetime.utcnow()
        
        # Create bot run record
        self.bot_run_record = BotRun(
            linkedin_account_id=self.account.id,
            bot_type=self.bot_type,
            status='running',
            start_time=self.start_time
        )
        db.session.add(self.bot_run_record)
        db.session.commit()
        
        log_bot_activity(self.bot_type, self.account.email, "Connection Request Bot started")
        
        try:
            # Login to LinkedIn
            if not self.login():
                self._update_run_status('failed', 'Login failed')
                return False
            
            # Get target profiles from recent Activity Bot results
            target_profiles = self._get_target_profiles()
            
            if not target_profiles:
                log_bot_activity(self.bot_type, self.account.email, 
                               "No target profiles found for connection requests", 'warning')
                self._update_run_status('completed', 'No targets found')
                return True
            
            # Send connection requests
            for profile in target_profiles:
                if self._should_stop():
                    break
                
                try:
                    success = self._send_connection_request(profile)
                    if success:
                        self.sent_requests += 1
                        log_bot_activity(self.bot_type, self.account.email, 
                                       f"Sent connection request to: {profile.name}")
                    
                    # Random delay between requests
                    self.random_delay(30, 60)
                    
                except Exception as e:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"Error sending request to {profile.name}: {str(e)}", 'error')
                    continue
            
            # Complete successfully
            self._update_run_status('completed', f'Sent {self.sent_requests} connection requests')
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Connection Request Bot completed. Sent: {self.sent_requests} requests")
            return True
            
        except Exception as e:
            error_msg = f"Connection Request Bot error: {str(e)}"
            self._update_run_status('failed', error_msg)
            log_bot_activity(self.bot_type, self.account.email, error_msg, 'error')
            return False
        
        finally:
            self.cleanup()
    
    def _get_target_profiles(self):
        """دریافت پروفایل‌های هدف برای ارسال درخواست کانکشن"""
        try:
            # Get profiles from recent posts (last 7 days)
            recent_date = datetime.utcnow() - timedelta(days=7)
            
            # Get profiles that haven't received connection requests yet
            target_profiles = db.session.query(Profile).join(Post).filter(
                Post.linkedin_account_id == self.account.id,
                Post.processed_at >= recent_date,
                ~Profile.id.in_(
                    db.session.query(SentInvitation.profile_id).filter(
                        SentInvitation.linkedin_account_id == self.account.id
                    )
                )
            ).limit(self.max_connections * 2).all()  # Get more than needed for selection
            
            # Shuffle and limit to max connections
            random.shuffle(target_profiles)
            return target_profiles[:self.max_connections]
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error getting target profiles: {str(e)}", 'error')
            return []
    
    def _send_connection_request(self, profile):
        """ارسال درخواست کانکشن به یک پروفایل"""
        try:
            # Navigate to profile
            self.driver.get(profile.profile_url)
            time.sleep(random.uniform(3, 5))
            
            # Find connect button
            connect_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(@aria-label, 'Connect') or contains(text(), 'Connect')]")
            
            if not connect_buttons:
                # Try alternative selectors
                connect_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button[data-control-name='connect']")
            
            if not connect_buttons:
                log_bot_activity(self.bot_type, self.account.email, 
                               f"Connect button not found for: {profile.name}", 'warning')
                return False
            
            # Click connect button
            connect_buttons[0].click()
            time.sleep(random.uniform(2, 4))
            
            # Handle personalized message dialog
            self._handle_connection_dialog(profile)
            
            # Save sent invitation record
            invitation = SentInvitation(
                linkedin_account_id=self.account.id,
                profile_id=profile.id,
                message="",  # Will be updated if personalized message was sent
                status='sent',
                sent_at=datetime.utcnow()
            )
            db.session.add(invitation)
            db.session.commit()
            
            return True
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error sending connection request to {profile.name}: {str(e)}", 'error')
            return False
    
    def _handle_connection_dialog(self, profile):
        """مدیریت دیالوگ پیام شخصی‌سازی شده"""
        try:
            # Wait for dialog to appear
            time.sleep(2)
            
            # Check if personalization dialog appeared
            personalize_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Add a note') or contains(text(), 'پیام')]")
            
            if personalize_buttons and random.random() < 0.3:  # 30% chance to personalize
                # Click add note button
                personalize_buttons[0].click()
                time.sleep(random.uniform(1, 2))
                
                # Find message textarea
                message_inputs = self.driver.find_elements(By.CSS_SELECTOR, 
                    "textarea[name='message']")
                
                if message_inputs:
                    # Personalized messages
                    messages = [
                        f"Hi {profile.name}, I'd love to connect and expand my professional network.",
                        f"Hello {profile.name}, I found your profile interesting and would like to connect.",
                        f"Hi {profile.name}, let's connect to share industry insights.",
                        f"Hello {profile.name}, I'd appreciate connecting with you.",
                        f"Hi {profile.name}, looking forward to connecting with like-minded professionals."
                    ]
                    
                    selected_message = random.choice(messages)
                    self.human_type(message_inputs[0], selected_message)
                    time.sleep(random.uniform(1, 2))
            
            # Find and click send button
            send_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Send') or contains(text(), 'ارسال')]")
            
            if send_buttons:
                send_buttons[0].click()
                time.sleep(random.uniform(2, 3))
                
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error handling connection dialog: {str(e)}", 'error')
    
    def _should_stop(self):
        """بررسی اینکه آیا ربات باید متوقف شود"""
        # Check connection limit
        if self.sent_requests >= self.max_connections:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Maximum connections reached ({self.max_connections})")
            return True
        
        # Check for rate limiting or challenges
        if "429" in self.driver.current_url or "challenge" in self.driver.current_url.lower():
            log_bot_activity(self.bot_type, self.account.email, "Rate limiting detected")
            return True
        
        return False
    
    def _update_run_status(self, status, error_message=None):
        """به‌روزرسانی وضعیت اجرا"""
        if self.bot_run_record:
            self.bot_run_record.status = status
            self.bot_run_record.end_time = datetime.utcnow()
            
            results = {
                'sent_requests': self.sent_requests,
                'max_limit': self.max_connections
            }
            self.bot_run_record.set_results(results)
            
            if error_message:
                self.bot_run_record.error_message = error_message
            
            db.session.commit()