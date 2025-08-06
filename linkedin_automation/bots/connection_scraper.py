import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.linkedin_bot_base import LinkedInBot
from utils.logging_config import log_bot_activity
from models import db, Profile, Connection, BotRun

class ConnectionScraper(LinkedInBot):
    """ربات استخراج کانکشن‌های فعلی"""
    
    def __init__(self, account):
        super().__init__(account, 'connection_scraper')
        self.scraped_connections = 0
        self.bot_run_record = None
    
    def run(self):
        """اجرای اصلی ربات استخراج کانکشن‌ها"""
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
        
        log_bot_activity(self.bot_type, self.account.email, "Connection Scraper started")
        
        try:
            # Login to LinkedIn
            if not self.login():
                self._update_run_status('failed', 'Login failed')
                return False
            
            # Navigate to connections page
            self.driver.get("https://www.linkedin.com/mynetwork/invite-connect/connections/")
            time.sleep(5)
            
            # Scrape connections
            self._scrape_all_connections()
            
            # Complete successfully
            self._update_run_status('completed', f'Scraped {self.scraped_connections} connections')
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Connection Scraper completed. Scraped: {self.scraped_connections}")
            return True
            
        except Exception as e:
            error_msg = f"Connection Scraper error: {str(e)}"
            self._update_run_status('failed', error_msg)
            log_bot_activity(self.bot_type, self.account.email, error_msg, 'error')
            return False
        
        finally:
            self.cleanup()
    
    def _scrape_all_connections(self):
        """استخراج تمام کانکشن‌ها"""
        try:
            page = 1
            while True:
                # Load connections on current page
                connection_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".mn-connection-card")
                
                if not connection_elements:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"No more connections found on page {page}")
                    break
                
                for element in connection_elements:
                    try:
                        self._process_connection_element(element)
                    except Exception as e:
                        log_bot_activity(self.bot_type, self.account.email, 
                                       f"Error processing connection: {str(e)}", 'error')
                        continue
                
                # Try to load next page
                if not self._load_next_page():
                    break
                
                page += 1
                time.sleep(3)
                
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error scraping connections: {str(e)}", 'error')
    
    def _process_connection_element(self, element):
        """پردازش یک المنت کانکشن"""
        try:
            # Extract profile data
            name_elements = element.find_elements(By.CSS_SELECTOR, 
                ".mn-connection-card__name")
            if not name_elements:
                return
            
            name = name_elements[0].text
            
            # Extract profile URL
            profile_links = element.find_elements(By.CSS_SELECTOR, 
                "a[href*='/in/']")
            if not profile_links:
                return
            
            profile_url = profile_links[0].get_attribute('href')
            
            # Extract LinkedIn profile ID
            profile_id = profile_url.split('/in/')[-1].split('/')[0]
            
            # Extract headline
            headline = ""
            headline_elements = element.find_elements(By.CSS_SELECTOR, 
                ".mn-connection-card__occupation")
            if headline_elements:
                headline = headline_elements[0].text
            
            # Check if profile already exists
            profile = Profile.query.filter_by(linkedin_profile_id=profile_id).first()
            
            if not profile:
                # Create new profile
                profile = Profile(
                    linkedin_profile_id=profile_id,
                    name=name,
                    headline=headline,
                    profile_url=profile_url
                )
                db.session.add(profile)
                db.session.flush()  # Get the ID
            else:
                # Update existing profile
                profile.name = name
                profile.headline = headline
                profile.profile_url = profile_url
            
            # Check if connection already exists
            existing_connection = Connection.query.filter_by(
                linkedin_account_id=self.account.id,
                profile_id=profile.id
            ).first()
            
            if not existing_connection:
                # Create new connection record
                connection = Connection(
                    linkedin_account_id=self.account.id,
                    profile_id=profile.id,
                    source='scraper',
                    connected_at=datetime.utcnow()
                )
                db.session.add(connection)
                self.scraped_connections += 1
            
            db.session.commit()
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error processing connection element: {str(e)}", 'error')
    
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
            
            results = {'scraped_connections': self.scraped_connections}
            self.bot_run_record.set_results(results)
            
            if error_message:
                self.bot_run_record.error_message = error_message
            
            db.session.commit()