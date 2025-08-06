import random
import time
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from utils.linkedin_bot_base import LinkedInBot
from utils.logging_config import log_bot_activity
from models import db, Profile, Post, Comment, BotRun

class ActivityBot(LinkedInBot):
    """ربات فعالیت - اسکرپ پست‌ها، لایک، کامنت و استخراج reposter ها"""
    
    def __init__(self, account):
        super().__init__(account, 'activity_bot')
        self.max_runtime_hours = 7  # Maximum 7 hours runtime
        self.start_time = None
        self.processed_posts = 0
        self.likes_count = 0
        self.comments_count = 0
        self.extracted_profiles = 0
        self.bot_run_record = None
    
    def run(self):
        """اجرای اصلی ربات فعالیت"""
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
        
        log_bot_activity(self.bot_type, self.account.email, "Activity Bot started")
        
        try:
            # Login to LinkedIn
            if not self.login():
                self._update_run_status('failed', 'Login failed')
                return False
            
            # Get keywords for this account
            keywords = [kw.keyword for kw in self.account.keywords if kw.is_active]
            blacklist = [bl.keyword for bl in self.account.blacklist if bl.is_active]
            
            if not keywords:
                log_bot_activity(self.bot_type, self.account.email, "No keywords found, using default search", 'warning')
                keywords = ['technology', 'business', 'innovation']
            
            # Process each keyword
            for keyword in keywords:
                if self._should_stop():
                    break
                
                self._search_and_process_posts(keyword, blacklist)
                self.random_delay(30, 60)  # Delay between keywords
            
            # Complete successfully
            self._update_run_status('completed', 'Activity Bot completed successfully')
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Activity Bot completed. Posts: {self.processed_posts}, "
                           f"Likes: {self.likes_count}, Comments: {self.comments_count}, "
                           f"Profiles: {self.extracted_profiles}")
            return True
            
        except Exception as e:
            error_msg = f"Activity Bot error: {str(e)}"
            self._update_run_status('failed', error_msg)
            log_bot_activity(self.bot_type, self.account.email, error_msg, 'error')
            return False
        
        finally:
            self.cleanup()
    
    def _search_and_process_posts(self, keyword, blacklist):
        """جستجو و پردازش پست‌ها برای یک کلیدواژه"""
        try:
            # Navigate to LinkedIn search
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={keyword}&sortBy=%22date_posted%22&datePosted=%22past-24h%22"
            self.driver.get(search_url)
            time.sleep(random.uniform(3, 5))
            
            # Scroll and load posts
            self._scroll_and_load_posts()
            
            # Get all post elements
            posts = self.driver.find_elements(By.CSS_SELECTOR, "[data-id^='urn:li:activity:']")
            log_bot_activity(self.bot_type, self.account.email, f"Found {len(posts)} posts for keyword: {keyword}")
            
            for post_element in posts:
                if self._should_stop():
                    break
                
                try:
                    self._process_single_post(post_element, keyword, blacklist)
                except Exception as e:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"Error processing post: {str(e)}", 'error')
                    continue
                
                # Random delay between posts
                self.random_delay(10, 20)
                
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error searching posts for keyword {keyword}: {str(e)}", 'error')
    
    def _process_single_post(self, post_element, keyword, blacklist):
        """پردازش یک پست"""
        try:
            # Extract post data
            post_data = self._extract_post_data(post_element)
            if not post_data:
                return
            
            # Check blacklist
            post_content = post_data.get('content', '').lower()
            for blacklist_word in blacklist:
                if blacklist_word.lower() in post_content:
                    log_bot_activity(self.bot_type, self.account.email, 
                                   f"Post skipped due to blacklist word: {blacklist_word}")
                    return
            
            # Save post to database
            post_record = self._save_post(post_data)
            if not post_record:
                return
            
            # Extract author profile
            if post_data.get('author_profile_url'):
                author_profile = self._extract_profile_data(post_data['author_profile_url'])
                if author_profile:
                    post_record.author_profile_id = author_profile.id
                    db.session.commit()
            
            # Perform engagement actions
            self._engage_with_post(post_element, post_record)
            
            # Extract reposter profiles
            self._extract_reposter_profiles(post_element)
            
            self.processed_posts += 1
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error processing single post: {str(e)}", 'error')
    
    def _extract_post_data(self, post_element):
        """استخراج داده‌های پست"""
        try:
            post_data = {}
            
            # Post ID
            post_id = post_element.get_attribute('data-id')
            if post_id:
                post_data['linkedin_post_id'] = post_id
            
            # Post content
            content_elements = post_element.find_elements(By.CSS_SELECTOR, 
                ".feed-shared-text__text-view span[aria-hidden='true']")
            if content_elements:
                post_data['content'] = content_elements[0].text
            
            # Author information
            author_elements = post_element.find_elements(By.CSS_SELECTOR, 
                ".feed-shared-actor__name a")
            if author_elements:
                post_data['author_name'] = author_elements[0].text
                post_data['author_profile_url'] = author_elements[0].get_attribute('href')
            
            # Post URL
            permalink_elements = post_element.find_elements(By.CSS_SELECTOR, 
                ".feed-shared-control-menu__trigger")
            if permalink_elements:
                # Extract post URL from permalink
                post_data['post_url'] = f"https://www.linkedin.com/feed/update/{post_id}/"
            
            # Engagement counts
            like_elements = post_element.find_elements(By.CSS_SELECTOR, 
                ".social-counts-reactions__count-value")
            if like_elements:
                try:
                    post_data['likes_count'] = int(like_elements[0].text.replace(',', ''))
                except:
                    post_data['likes_count'] = 0
            
            comment_elements = post_element.find_elements(By.CSS_SELECTOR, 
                ".social-counts-comments .social-counts__item-count")
            if comment_elements:
                try:
                    post_data['comments_count'] = int(comment_elements[0].text.replace(',', ''))
                except:
                    post_data['comments_count'] = 0
            
            return post_data
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error extracting post data: {str(e)}", 'error')
            return None
    
    def _save_post(self, post_data):
        """ذخیره پست در دیتابیس"""
        try:
            # Check if post already exists
            existing_post = Post.query.filter_by(
                linkedin_post_id=post_data['linkedin_post_id']
            ).first()
            
            if existing_post:
                return existing_post
            
            # Create new post record
            post = Post(
                linkedin_account_id=self.account.id,
                linkedin_post_id=post_data['linkedin_post_id'],
                content=post_data.get('content', ''),
                post_url=post_data.get('post_url', ''),
                likes_count=post_data.get('likes_count', 0),
                comments_count=post_data.get('comments_count', 0),
                processed_at=datetime.utcnow()
            )
            
            db.session.add(post)
            db.session.commit()
            
            return post
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error saving post: {str(e)}", 'error')
            return None
    
    def _extract_profile_data(self, profile_url):
        """استخراج داده‌های پروفایل"""
        try:
            # Extract LinkedIn profile ID from URL
            profile_id_match = profile_url.split('/in/')[-1].split('/')[0]
            
            # Check if profile already exists
            existing_profile = Profile.query.filter_by(
                linkedin_profile_id=profile_id_match
            ).first()
            
            if existing_profile:
                return existing_profile
            
            # Visit profile to extract data (be careful about rate limits)
            self.driver.get(profile_url)
            time.sleep(random.uniform(3, 5))
            
            profile_data = {
                'linkedin_profile_id': profile_id_match,
                'profile_url': profile_url
            }
            
            # Extract name
            name_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                "h1.text-heading-xlarge")
            if name_elements:
                profile_data['name'] = name_elements[0].text
            
            # Extract headline
            headline_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                ".text-body-medium.break-words")
            if headline_elements:
                profile_data['headline'] = headline_elements[0].text
            
            # Extract location
            location_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                ".text-body-small.inline.t-black--light.break-words")
            if location_elements:
                profile_data['location'] = location_elements[0].text
            
            # Create profile record
            profile = Profile(
                linkedin_profile_id=profile_data['linkedin_profile_id'],
                name=profile_data.get('name', ''),
                headline=profile_data.get('headline', ''),
                location=profile_data.get('location', ''),
                profile_url=profile_data['profile_url']
            )
            
            db.session.add(profile)
            db.session.commit()
            
            self.extracted_profiles += 1
            return profile
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error extracting profile data: {str(e)}", 'error')
            return None
    
    def _engage_with_post(self, post_element, post_record):
        """تعامل با پست (لایک و کامنت)"""
        try:
            # Like the post (70% chance)
            if random.random() < 0.7:
                like_buttons = post_element.find_elements(By.CSS_SELECTOR, 
                    "button[aria-label*='like']")
                if like_buttons and not "aria-pressed=\"true\"" in like_buttons[0].get_attribute('outerHTML'):
                    like_buttons[0].click()
                    self.likes_count += 1
                    log_bot_activity(self.bot_type, self.account.email, f"Liked post: {post_record.linkedin_post_id}")
                    time.sleep(random.uniform(1, 3))
            
            # Comment on the post (20% chance)
            if random.random() < 0.2:
                self._add_comment_to_post(post_element, post_record)
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error engaging with post: {str(e)}", 'error')
    
    def _add_comment_to_post(self, post_element, post_record):
        """اضافه کردن کامنت به پست"""
        try:
            # Generic positive comments in Persian and English
            comments = [
                "Great insight! 👍",
                "Thanks for sharing this valuable information.",
                "Very helpful post!",
                "نظر بسیار جالبی است. ممنون از اشتراک‌گذاری.",
                "مطلب مفیدی بود. سپاس!",
                "Excellent point of view!",
                "This is exactly what I was looking for.",
                "Amazing content, keep it up!",
                "بسیار آموزنده بود.",
                "Perfect timing for this post!"
            ]
            
            # Find comment button
            comment_buttons = post_element.find_elements(By.CSS_SELECTOR, 
                "button[aria-label*='comment']")
            if not comment_buttons:
                return
            
            comment_buttons[0].click()
            time.sleep(random.uniform(2, 4))
            
            # Find comment input
            comment_inputs = self.driver.find_elements(By.CSS_SELECTOR, 
                "div[contenteditable='true'][role='textbox']")
            if not comment_inputs:
                return
            
            # Select random comment
            selected_comment = random.choice(comments)
            
            # Type comment
            comment_input = comment_inputs[-1]  # Get the last one (most recent)
            self.human_type(comment_input, selected_comment)
            time.sleep(random.uniform(1, 2))
            
            # Find and click post button
            post_buttons = self.driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Post') or contains(text(), 'ارسال')]")
            if post_buttons:
                post_buttons[-1].click()
                
                # Save comment to database
                comment_record = Comment(
                    linkedin_account_id=self.account.id,
                    post_id=post_record.id,
                    content=selected_comment,
                    status='sent'
                )
                db.session.add(comment_record)
                db.session.commit()
                
                self.comments_count += 1
                log_bot_activity(self.bot_type, self.account.email, 
                               f"Added comment to post: {post_record.linkedin_post_id}")
                time.sleep(random.uniform(3, 5))
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error adding comment: {str(e)}", 'error')
    
    def _extract_reposter_profiles(self, post_element):
        """استخراج پروفایل‌های reposter ها"""
        try:
            # This would involve clicking on repost count and extracting profiles
            # Implementation would be similar to profile extraction
            # For now, we'll skip this to avoid complexity
            pass
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error extracting reposter profiles: {str(e)}", 'error')
    
    def _scroll_and_load_posts(self):
        """اسکرول و بارگذاری پست‌ها"""
        try:
            # Scroll down to load more posts
            for i in range(3):  # Scroll 3 times
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
            
            # Scroll back up
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
        except Exception as e:
            log_bot_activity(self.bot_type, self.account.email, 
                           f"Error scrolling posts: {str(e)}", 'error')
    
    def _should_stop(self):
        """بررسی اینکه آیا ربات باید متوقف شود"""
        # Check runtime limit
        if self.start_time:
            runtime = datetime.utcnow() - self.start_time
            if runtime.total_seconds() > (self.max_runtime_hours * 3600):
                log_bot_activity(self.bot_type, self.account.email, 
                               f"Maximum runtime reached ({self.max_runtime_hours} hours)")
                return True
        
        # Check for 429 error (rate limiting)
        if "429" in self.driver.current_url or "challenge" in self.driver.current_url.lower():
            log_bot_activity(self.bot_type, self.account.email, "Rate limiting detected (429)")
            return True
        
        return False
    
    def _update_run_status(self, status, error_message=None):
        """به‌روزرسانی وضعیت اجرا"""
        if self.bot_run_record:
            self.bot_run_record.status = status
            self.bot_run_record.end_time = datetime.utcnow()
            
            results = {
                'processed_posts': self.processed_posts,
                'likes_count': self.likes_count,
                'comments_count': self.comments_count,
                'extracted_profiles': self.extracted_profiles
            }
            self.bot_run_record.set_results(results)
            
            if error_message:
                self.bot_run_record.error_message = error_message
            
            db.session.commit()