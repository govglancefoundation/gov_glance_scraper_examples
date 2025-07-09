# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from readability import Document
from markdownify import markdownify as md 
import dateutil.parser
import pytz
import re
import html
from urllib.parse import urlparse
from w3lib.html import remove_tags
import json
import logging
from scrapy.utils.project import get_project_settings
import psycopg2
from psycopg2 import errors

from news_crawler.items import NotificationModel

def rank_urls_for_articles(urls_list):
    """
    Ranks a list of URLs based on their likelihood of being individual articles,
    and returns only the most likely ones.
    """
    # --- Configuration ---
    ARTICLE_INDICATORS_WEIGHTS = {
        # Regex patterns for dates (strong positive signals)
        r'/\d{4}/\d{2}/\d{2}/': 5,  # /YYYY/MM/DD/
        r'/\d{4}-\d{2}-\d{2}/': 5,   # /YYYY-MM-DD/
        r'/\d{4}/\d{2}/': 2,         # /YYYY/MM/ (weaker, usually needs a slug after)
        
        # Common content type slugs (string segments)
        'article': 4,
        'issues': 4,
        'blog': 4,
        'news': 3,
        'post': 3,
        'story': 3,
        'media': 3,
        'press-release': 3,
        'media-release': 3,
        'speech': 3,
        'report': 3,
        'paper': 3,
        'document': 2,
        'publication': 2,
        'release': 2,
        
        # Government/official content patterns
        'announcement': 3,
        'update': 2,
        'statement': 3,
        'advisory': 3,
        'notice': 2,
        'bulletin': 3,
        
        # Event/time-sensitive indicators
        'month': 2,  # like "safety-awareness-month"
        'week': 2,   # like "national-xyz-week"
        'day': 2,    # like "international-xyz-day"
        'annual': 2,
        '2024': 2,   # Current/recent year
        '2025': 2,
        '2023': 1,   # Slightly older years
    }
    
    NON_ARTICLE_INDICATORS_WEIGHTS = {
        # Common navigational/category terms
        'category': -3,
        'tag': -3,
        'archive': -2,
        '/page/': -2,
        'list': -2,
        'search': -3,
        'collection': -2,
        'series': -2,
        'topic': -2,
        
        # Common administrative/site structure terms
        'about': -1,
        'contact': -1,
        'privacy': -1,
        'terms': -1,
        'dashboard': -4,
        'admin': -5,
        'login': -5,
        'signup': -3,
        'cart': -2,
        'checkout': -2,
        'sitemap': -2,
        'feed': -1,
        'json': -1,
        'xml': -1,
        'amp': -1,
        'main-content': -3,
        
        # Index/home pages
        'index': -2,
        'home': -2,
        'default': -2,
    }
    
    # Additional slug quality patterns
    SLUG_QUALITY_PATTERNS = {
        # Long, hyphenated slugs (like "atv-off-highway-vehicle-safety-awareness-month-3")
        r'[-\w]{20,}': 3,  # Slugs with 20+ characters
        r'\w+-\w+-\w+-\w+': 2,  # At least 4 words separated by hyphens
        r'-\d+/?$': 1,  # Ends with a number (version/part indicator)
        
        # Specific content patterns
        r'(safety|awareness|education|training|program|initiative)': 1,
        r'(guide|tips|advice|how-to|faq)': 2,
    }
    
    # Domain-specific bonuses
    DOMAIN_BONUSES = {
        '.gov': 1,  # Government sites often have articles without typical indicators
        '.edu': 1,  # Educational sites similar pattern
        '.org': 0.5,  # Non-profits sometimes similar
    }
    
    MIN_PATH_SEGMENTS = 2
    MIN_ARTICLE_SCORE_THRESHOLD = 5
    
    likely_articles_with_scores = []
    
    for url in urls_list:
        current_score = 0
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        domain = parsed_url.netloc.lower()
        
        # Path segment count heuristic
        path_segments = path.split('/') if path else []
        path_segments_count = len(path_segments)
        
        # Check for domain-specific bonuses
        for domain_pattern, bonus in DOMAIN_BONUSES.items():
            if domain.endswith(domain_pattern):
                current_score += bonus
                
        # Apply Positive Indicators
        for indicator, weight in ARTICLE_INDICATORS_WEIGHTS.items():
            if indicator.startswith(r'/') and indicator.endswith(r'/'):  # Regex pattern
                if re.search(indicator, url):
                    current_score += weight
            elif indicator in url.lower():  # Case-insensitive string check
                # Check for whole segment match for better accuracy
                if f'/{indicator}/' in url or url.endswith(f'/{indicator}') or url.startswith(f'{indicator}/'):
                    current_score += weight
                    
        # Apply slug quality patterns
        if path_segments:
            last_segment = path_segments[-1]
            for pattern, weight in SLUG_QUALITY_PATTERNS.items():
                if re.search(pattern, last_segment, re.IGNORECASE):
                    current_score += weight
                    
            # Bonus for slugs that look like titles (multiple hyphenated words)
            hyphen_count = last_segment.count('-')
            if hyphen_count >= 3:
                current_score += min(hyphen_count - 2, 3)  # Cap at +3
                
        # Apply Negative Indicators
        for indicator, weight in NON_ARTICLE_INDICATORS_WEIGHTS.items():
            if indicator.startswith(r'/') and indicator.endswith(r'/'):  # Regex pattern
                if re.search(indicator, url):
                    current_score += weight
            elif indicator in url.lower():  # Case-insensitive string check
                if (f'/{indicator}/' in url or url.endswith(f'/{indicator}') or url.startswith(f'{indicator}/') or
                    (indicator == '#' and '#' in url) or
                    (indicator == '/page/' and re.search(r'/page/\d+', url))):
                    current_score += weight
                    
        # Apply Minimum Path Segment Length Heuristic
        if path_segments_count < MIN_PATH_SEGMENTS:
            current_score -= 3
        elif path_segments_count > MIN_PATH_SEGMENTS + 1:
            current_score += min(path_segments_count - MIN_PATH_SEGMENTS, 2)
            
        # Special case: if URL has no typical article indicators but has a long, descriptive slug
        if current_score < MIN_ARTICLE_SCORE_THRESHOLD and path_segments:
            last_segment = path_segments[-1]
            # Check if it's a long, descriptive slug (like your example)
            if len(last_segment) > 30 and '-' in last_segment:
                word_count = len(last_segment.split('-'))
                if word_count >= 5:
                    current_score += 3  # Significant boost for long, descriptive slugs
                    
        # Final Filtering
        if current_score >= MIN_ARTICLE_SCORE_THRESHOLD:
            likely_articles_with_scores.append({'url': url, 'score': current_score})
            
    # Sort results by score in descending order
    likely_articles_with_scores.sort(key=lambda x: x['score'], reverse=True)
    
    return likely_articles_with_scores

def is_relative_url(url):
    """
    Check if a URL is relative.
    Returns True for relative URLs, False for absolute URLs.
    
    Examples:
        is_relative_url('/about') -> True
        is_relative_url('page.html') -> True
        is_relative_url('https://example.com') -> False
        is_relative_url('//example.com/path') -> False
    """
    parsed = urlparse(url)
    # A relative URL won't have a netloc (domain) or scheme (http/https)
    return not (parsed.netloc or parsed.scheme)

def remove_script_tags(text):
    # Remove JavaScript code
    text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL)
    
    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    
    # Decode HTML entities like &#8230;
    text = html.unescape(text)
    
    return text

def clean_text(text):
    # Split by 'Tags' and take only the content before it
    main_content = text.split('Tags')[0]
    
    # Remove extra whitespace, newlines and tabs
    cleaned = ' '.join(main_content.split())
    
    return cleaned.strip()

def convert_to_utc(date_string):
    """
    Convert a date string to UTC timezone.
    If the string has no timezone info, it assumes local time and converts to UTC.
    If it already has timezone info, it converts that to UTC.
    """
    # Parse the date string
    dt = dateutil.parser.parse(date_string)
    
    # Check if the datetime already has timezone info
    if dt.tzinfo is None:
        # If no timezone info, assume it's in local time
        # and add the local timezone
        local_tz = pytz.timezone('America/New_York')  # Change to your local timezone
        dt = local_tz.localize(dt)
    
    # Convert to UTC
    utc_dt = dt.astimezone(pytz.UTC)
    
    return utc_dt


class NewsCrawlerPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        field_names = adapter.field_names()

        for field_name in field_names:
            if field_name in adapter:
                if field_name == 'created_at':
                    value = adapter[field_name]
                    adapter[field_name] = dateutil.parser.parse(value)
                if field_name == 'description':
                    value = adapter[field_name]
                    adapter[field_name] = clean_text(remove_tags(remove_script_tags(html.unescape(value))))
                if field_name == 'encoded':
                    value = adapter[field_name]
                    adapter[field_name] = clean_text(remove_tags(remove_script_tags(html.unescape(value))))
                if field_name == 'source_text':
                    value = adapter[field_name]
                    adapter[field_name] = json.dumps(clean_text(remove_tags(remove_script_tags(html.unescape(value)))))
                if field_name == 'response':
                    value = adapter[field_name]
                    adapter[field_name] = json.dumps(clean_text(remove_tags(remove_script_tags(html.unescape(value)))))
                if field_name == 'title':
                    value = adapter[field_name]
                    adapter[field_name] = value.lstrip().rstrip()
                if field_name == 'event_location':
                    value = adapter[field_name]

                    adapter[field_name] = ' '.join(value.split())
                if field_name == 'md':
                    value = adapter.get(field_name)
                    if value:
                        doc = Document(value)
                        clean_html = doc.summary()
                        adapter[field_name] = md(clean_html)
        return item
    
class WriteToDbPipeline:

    def __init__(self):
        POSTGRES_USERNAME = get_project_settings().get('POSTGRES_USERNAME')
        POSTGRES_PASS = get_project_settings().get('POSTGRES_PASSWORD')
        POSTGRES_ADDRESS = get_project_settings().get('POSTGRES_ADDRESS')
        POSTGRES_PORT = get_project_settings().get('POSTGRES_PORT')
        POSTGRES_DBNAME = get_project_settings().get('POSTGRES_DBNAME')

        self.schema = "united_states_of_america"
        self.connection = psycopg2.connect(
            user=POSTGRES_USERNAME,
            password=POSTGRES_PASS,
            host=POSTGRES_ADDRESS,
            port=POSTGRES_PORT,
            database=POSTGRES_DBNAME
        )
        self.cur = self.connection.cursor()

    def process_item(self, item, spider):

        item_with_notification = item.copy()
        table_name = item['table_name'].lower().replace(' ', '_')
        try:
            del item['notification']
            logging.info('item after the delete', item)
            columns = ', '.join(item.keys())
            values = ', '.join('%({})s'.format(key) for key in item.keys())
            query = f"INSERT INTO {self.schema}.{table_name} ({columns}) VALUES ({values}) RETURNING id"
            # print(query)
            self.cur.execute(query, item)
            database_table_id = self.cur.fetchone()[0]
            print(database_table_id, item)
            logging.info('stored item with notification variable',item_with_notification)
            if item_with_notification['notification'] == True:
                self.connection.commit()
                logging.info('This item requires a notification')
                return NotificationModel(
                    {
                        'title': item_with_notification.get('title', None),
                        'table_id': database_table_id,
                        'country_schema': self.schema,
                        'table_source_name': table_name,
                        'image_url': item_with_notification.get('image_url', None),
                        'description': item_with_notification.get('description', None),
                        'topic': item_with_notification.get('topic', None),
                        'collection_name': item_with_notification.get('collection_name', None),
                        # 'notification': item_with_notification.get('notification', None)
                    }
                )
            else:
                logging.info(f"Item inserted to {self.schema}.{table_name} with id {database_table_id}")
                self.connection.commit()
        except errors.UndefinedTable as e:
            self.does_table_exist(item)
            # Handle the UndefinedTable exception here
            logging.critical(f"{e}: The table {table_name} does not exist.")
            return None
        except errors.UndefinedColumn as e:
            error_msg = str(e)
            match = re.search(r'column "([^"]+)" of relation', error_msg)

            if match:
                undefined_column = match.group(1)
                print(undefined_column)
                self.column_does_not_exist(item,undefined_column)
                logging.critical(f"The column {undefined_column} does not exist for table: {table_name}.")

                return None
        except psycopg2.Error as e:
                
            self.connection.rollback()
            logging.critical("Error: ", e)

        except psycopg2.ProgrammingError as e:
            if "can't adapt type 'Tag'" in str(e):
                print("Error: Cannot convert Tag object to database format. Please convert to string or other basic type first.")
                # Optional: print more details about the Tag object
                print(f"Problematic Tag object: ")

            else:
                # Handle other programming errors
                print(f"Database programming error: {e}")
    def close_spider(self, spider):
        self.cur.close()
        self.connection.close()