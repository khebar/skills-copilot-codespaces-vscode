import time
from datetime import datetime
from selenium.webdriver.common.by import By

from utils.linkedin_bot_base import LinkedInBot
from utils.logging_config import log_bot_activity
from models import db, Profile, SentInvitation, BotRun

class SentInvitationsScraper(LinkedInBot):
    """ربات استخراج دعوتنامه‌های ارسالی"""
    
    def __init__(self, account):
        super().__init__(account, 'sent_invitations_scraper')
        self.scraped_invitations = 0
        self.bot_run_record = None
    
    def run(self):
        """اجرای اصلی ربات استخراج دعوتنامه‌های ارسالی"""
        start_time = datetime.utcnow()
        
        # Create bot run record
        self.bot_run_record = BotRun(
            linkedin_account_id=self.account.id,
            bot_type=self.bot_type,
            status='running',
            start_time=start_time
        )
        db.session.add(self.bot_run_record)
        db.session.commit()
        
        log_bot_activity(self.bot_type, self.account.email, "Sent Invitations Scraper started")
        
        try:
            # Login to LinkedIn
            if not self.login():
                self._update_run_status('failed', 'Login failed')
                return False
            
            # Navigate to sent invitations page
            self.driver.get("https://www.linkedin.com/mynetwork/invitation-manager/sent/")
            time.sleep(5)
            
            # Scrape sent invitations
            self._scrape_all_sent_invitations()
            
            # Complete successfully
            self._update_run_status('completed', f'Scraped {self.scraped_invitations} sent invitations')
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Sent Invitations Scraper completed. Scraped: {self.scraped_invitations}")
            return True
            
        except Exception as e:
            error_msg = f"Sent Invitations Scraper error: {str(e)}"
            self._update_run_status('failed', error_msg)
            log_bot_activity(self.bot_type, self.account.email, error_msg, 'error')
            return False
        
        finally:
            self.cleanup()
    
    def _scrape_all_sent_invitations(self):
        """استخراج تمام دعوتنامه‌های ارسالی"""
        try:
            page = 1
            while True:
                # Load invitations on current page
                invitation_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".invitation-card")
                
                if not invitation_elements:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"No more sent invitations found on page {page}")
                    break
                
                for element in invitation_elements:
                    try:
                        self._process_invitation_element(element)
                    except Exception as e:
                        log_bot_activity(self.bot_type, self.account.email, 
                                       f"Error processing invitation: {str(e)}", 'error')
                        continue
                
                # Try to load next page
                if not self._load_next_page():
                    break
                
                page += 1
                time.sleep(3)
                
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error scraping sent invitations: {str(e)}", 'error')
    
    def _process_invitation_element(self, element):
        """پردازش یک المنت دعوتنامه ارسالی"""
        try:
            # Extract profile data
            name_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__name")
            if not name_elements:
                return
            
            name = name_elements[0].text
            
            # Extract profile URL
            profile_links = element.find_elements(By.CSS_SELECTOR, 
                "a[href*='/in/']")
            if not profile_links:
                return
            
            profile_url = profile_links[0].get_attribute('href')
            profile_id = profile_url.split('/in/')[-1].split('/')[0]
            
            # Extract status
            status = 'sent'  # Default status
            status_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__status")
            if status_elements:
                status_text = status_elements[0].text.lower()
                if 'accepted' in status_text or 'پذیرفته' in status_text:
                    status = 'accepted'
                elif 'declined' in status_text or 'رد شده' in status_text:
                    status = 'declined'
                elif 'withdrawn' in status_text or 'لغو شده' in status_text:
                    status = 'withdrawn'
            
            # Extract message if available
            message = ""
            message_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__message")
            if message_elements:
                message = message_elements[0].text
            
            # Get or create profile
            profile = Profile.query.filter_by(linkedin_profile_id=profile_id).first()
            if not profile:
                profile = Profile(
                    linkedin_profile_id=profile_id,
                    name=name,
                    profile_url=profile_url
                )
                db.session.add(profile)
                db.session.flush()
            
            # Check if invitation already exists
            existing_invitation = SentInvitation.query.filter_by(
                linkedin_account_id=self.account.id,
                profile_id=profile.id
            ).first()
            
            if not existing_invitation:
                # Create new invitation record
                invitation = SentInvitation(
                    linkedin_account_id=self.account.id,
                    profile_id=profile.id,
                    message=message,
                    status=status,
                    sent_at=datetime.utcnow()
                )
                db.session.add(invitation)
                self.scraped_invitations += 1
            else:
                # Update existing invitation
                existing_invitation.status = status
                existing_invitation.message = message
            
            db.session.commit()
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error processing invitation element: {str(e)}", 'error')
    
    def _load_next_page(self):
        """بارگذاری صفحه بعدی"""
        try:
            # Scroll down to load more
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Check if "Show more results" button exists
            show_more_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Show more') or contains(text(), 'نمایش بیشتر')]")
            
            if show_more_buttons:
                show_more_buttons[0].click()
                time.sleep(5)
                return True
            
            return False
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error loading next page: {str(e)}", 'error')
            return False
    
    def _update_run_status(self, status, error_message=None):
        """به‌روزرسانی وضعیت اجرا"""
        if self.bot_run_record:
            self.bot_run_record.status = status
            self.bot_run_record.end_time = datetime.utcnow()
            
            results = {'scraped_invitations': self.scraped_invitations}
            self.bot_run_record.set_results(results)
            
            if error_message:
                self.bot_run_record.error_message = error_message
            
            db.session.commit()