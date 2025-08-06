import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import Config
from utils.logging_config import log_bot_activity

class LinkedInBot:
    """Base class for all LinkedIn bots"""
    
    def __init__(self, account, bot_type):
        self.account = account
        self.bot_type = bot_type
        self.driver = None
        self.session = requests.Session()
        self.is_logged_in = False
        
        # Setup session headers
        self.session.headers.update({
            'User-Agent': random.choice(Config.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
    
    def setup_driver(self, headless=True):
        """Setup Chrome WebDriver with security configurations"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
        
        # Security and performance options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-javascript')  # Will be enabled selectively
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument(f'--user-agent={random.choice(Config.USER_AGENTS)}')
        
        # Window size
        chrome_options.add_argument('--window-size=1366,768')
        
        try:
            self.driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.driver.implicitly_wait(10)
            log_bot_activity(self.bot_type, self.account.email, "WebDriver initialized successfully")
            return True
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, f"Failed to initialize WebDriver: {str(e)}", 'error')
            return False
    
    def login(self):
        """Login to LinkedIn using stored cookies or credentials"""
        try:
            if not self.driver:
                if not self.setup_driver():
                    return False
            
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(random.uniform(2, 4))
            
            # Try to use stored cookies first
            cookies = self.account.get_cookies()
            if cookies:
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except:
                        continue
                
                self.driver.refresh()
                time.sleep(3)
                
                # Check if logged in
                if self.is_logged_in_check():
                    self.is_logged_in = True
                    log_bot_activity(self.bot_type, self.account.email, "Logged in using stored cookies")
                    return True
            
            # Login with credentials if cookies failed
            return self.credential_login()
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, f"Login failed: {str(e)}", 'error')
            return False
    
    def credential_login(self):
        """Login using email and password"""
        try:
            # Find login form elements
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            
            # Enter credentials with human-like typing
            self.human_type(email_field, self.account.email)
            time.sleep(random.uniform(1, 2))
            
            self.human_type(password_field, self.account.password)
            time.sleep(random.uniform(1, 2))
            
            # Click login
            login_button.click()
            time.sleep(random.uniform(3, 5))
            
            # Handle potential security checks
            if self.handle_security_check():
                time.sleep(5)
            
            # Verify login success
            if self.is_logged_in_check():
                self.is_logged_in = True
                self.save_cookies()
                log_bot_activity(self.bot_type, self.account.email, "Successfully logged in with credentials")
                return True
            else:
                log_bot_activity(self.bot_type, self.account.email, "Login verification failed", 'error')
                return False
                
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, f"Credential login failed: {str(e)}", 'error')
            return False
    
    def is_logged_in_check(self):
        """Check if successfully logged in"""
        try:
            # Check for elements that indicate successful login
            indicators = [
                "//nav[@class='global-nav']",
                "//a[@data-control-name='identity_welcome_message']",
                "//button[@id='global-nav-search']"
            ]
            
            for indicator in indicators:
                try:
                    self.driver.find_element(By.XPATH, indicator)
                    return True
                except:
                    continue
            return False
        except:
            return False
    
    def handle_security_check(self):
        """Handle LinkedIn security challenges"""
        try:
            # Check for challenge page
            if "challenge" in self.driver.current_url.lower():
                log_bot_activity(self.bot_type, self.account.email, "Security challenge detected", 'warning')
                time.sleep(30)  # Wait for manual intervention or auto-resolution
                return True
            return False
        except:
            return False
    
    def save_cookies(self):
        """Save current cookies to database"""
        try:
            cookies = self.driver.get_cookies()
            self.account.set_cookies(cookies)
            
            # Also update CSRF token if present
            csrf_elements = self.driver.find_elements(By.NAME, "csrfToken")
            if csrf_elements:
                self.account.csrf_token = csrf_elements[0].get_attribute("value")
            
            # Save to database
            from models import db
            db.session.commit()
            
            log_bot_activity(self.bot_type, self.account.email, "Cookies saved successfully")
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, f"Failed to save cookies: {str(e)}", 'error')
    
    def human_type(self, element, text):
        """Type text in a human-like manner"""
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
    
    def random_delay(self, min_seconds=None, max_seconds=None):
        """Add random delay between actions"""
        if min_seconds is None:
            min_seconds = Config.BOT_DELAY_MIN
        if max_seconds is None:
            max_seconds = Config.BOT_DELAY_MAX
        
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        return delay
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
            log_bot_activity(self.bot_type, self.account.email, "Bot cleanup completed")
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, f"Cleanup error: {str(e)}", 'error')
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()