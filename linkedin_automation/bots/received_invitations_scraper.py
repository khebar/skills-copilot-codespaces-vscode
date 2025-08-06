import time
from datetime import datetime
from selenium.webdriver.common.by import By

from utils.linkedin_bot_base import LinkedInBot
from utils.logging_config import log_bot_activity
from models import db, Profile, ReceivedInvitation, BotRun

class ReceivedInvitationsScraper(LinkedInBot):
    """ربات استخراج دعوتنامه‌های دریافتی"""
    
    def __init__(self, account):
        super().__init__(account, 'received_invitations_scraper')
        self.scraped_invitations = 0
        self.bot_run_record = None
    
    def run(self):
        """اجرای اصلی ربات استخراج دعوتنامه‌های دریافتی"""
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
        
        log_bot_activity(self.bot_type, self.account.email, "Received Invitations Scraper started")
        
        try:
            # Login to LinkedIn
            if not self.login():
                self._update_run_status('failed', 'Login failed')
                return False
            
            # Navigate to received invitations page  
            self.driver.get("https://www.linkedin.com/mynetwork/invitation-manager/")
            time.sleep(5)
            
            # Scrape received invitations
            self._scrape_all_received_invitations()
            
            # Complete successfully
            self._update_run_status('completed', f'Scraped {self.scraped_invitations} received invitations')
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Received Invitations Scraper completed. Scraped: {self.scraped_invitations}")
            return True
            
        except Exception as e:
            error_msg = f"Received Invitations Scraper error: {str(e)}"
            self._update_run_status('failed', error_msg)
            log_bot_activity(self.bot_type, self.account.email, error_msg, 'error')
            return False
        
        finally:
            self.cleanup()
    
    def _scrape_all_received_invitations(self):
        """استخراج تمام دعوتنامه‌های دریافتی"""
        try:
            page = 1
            while True:
                # Load invitations on current page
                invitation_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".invitation-card, .mn-invitation-card")
                
                if not invitation_elements:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"No more received invitations found on page {page}")
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
                           f"Error scraping received invitations: {str(e)}", 'error')
    
    def _process_invitation_element(self, element):
        """پردازش یک المنت دعوتنامه دریافتی"""
        try:
            # Extract profile data
            name_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__name, .mn-invitation-card__name")
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
            
            # Extract headline
            headline = ""
            headline_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__headline, .mn-invitation-card__headline")
            if headline_elements:
                headline = headline_elements[0].text
            
            # Extract message if available
            message = ""
            message_elements = element.find_elements(By.CSS_SELECTOR, 
                ".invitation-card__message, .mn-invitation-card__message")
            if message_elements:
                message = message_elements[0].text
            
            # Determine status
            status = 'received'  # Default for received invitations
            
            # Get or create profile
            profile = Profile.query.filter_by(linkedin_profile_id=profile_id).first()
            if not profile:
                profile = Profile(
                    linkedin_profile_id=profile_id,
                    name=name,
                    headline=headline,
                    profile_url=profile_url
                )
                db.session.add(profile)
                db.session.flush()
            else:
                # Update profile info
                profile.name = name
                profile.headline = headline
                profile.profile_url = profile_url
            
            # Check if invitation already exists
            existing_invitation = ReceivedInvitation.query.filter_by(
                linkedin_account_id=self.account.id,
                profile_id=profile.id
            ).first()
            
            if not existing_invitation:
                # Create new invitation record
                invitation = ReceivedInvitation(
                    linkedin_account_id=self.account.id,
                    profile_id=profile.id,
                    message=message,
                    status=status,
                    received_at=datetime.utcnow()
                )
                db.session.add(invitation)
                self.scraped_invitations += 1
            else:
                # Update existing invitation
                existing_invitation.message = message
                existing_invitation.status = status
            
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