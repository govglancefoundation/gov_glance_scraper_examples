import scrapy
import os, json
from scrapy.http import Request, HtmlResponse
from bs4 import BeautifulSoup
from scrapy.linkextractors import LinkExtractor
from urllib.parse import urlparse
from news_crawler.items import NewsItems
from news_crawler.pipelines import rank_urls_for_articles
from trafilatura import extract


class GovNewsSpider(scrapy.Spider):
    name = "gov_news"

    def start_requests(self):

        # data_feed = GetFeedsPipeline().get_url_sources('xml')
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, '../html/united_states.json')
        with open(file_path, encoding='utf-8') as data_file:
            data_feed = json.load(data_file)

        for feed_data in data_feed[:5]:  # Try with fewer sites first
            request = Request(
                feed_data['source_url'], 
                meta = {
                     'items': feed_data,
                     # Mark this request as having a Firecrawl fallback option
                      
                    "zyte_api_automap": {
                    "browserHtml": True,
                    'screenshot': True,
                }
                }
            )
            yield request 


    def parse(self, response):

        soup = BeautifulSoup(response.text, 'html.parser')

        for selector in ['header', 'nav', 'footer', 'aside', '.sidebar', '.footer', '.header', '.nav', '.sidenav', 'sidebar', '.pagination', '.pager', '.related-links', '.related-posts','comments', '.comment', '.share-buttons', '.social-links', '.ad', '.advertisement', '.promo', '.promotion']:
            for element in soup.select(selector):
                element.decompose()

        processed_response = HtmlResponse(url=response.url, body=str(soup), encoding='utf-8')

        le = LinkExtractor()
        all_links = le.extract_links(processed_response)
        # print(all_links)
        parsed_urls_features = []
        for link in all_links:
            url = link.url
            # print(url)
            parsed = urlparse(url)
            
            # Skip URLs that don't contain .gov or .au
            if not ('.gov' in parsed.netloc.lower() or '.au' in parsed.netloc.lower()):
                continue  # Skip this URL
                
            # Skip social media domains
            social_media_domains = [
                'facebook.com', 'www.facebook.com',
                'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com',
                'reddit.com', 'www.reddit.com',
                'instagram.com', 'www.instagram.com',
                'linkedin.com', 'www.linkedin.com',
                'youtube.com', 'www.youtube.com',
                'tiktok.com', 'www.tiktok.com',
                'pinterest.com', 'www.pinterest.com',
                'tumblr.com', 'www.tumblr.com',
                'snapchat.com', 'www.snapchat.com',
                'threads.net', 'www.threads.net'
            ]

            if parsed.netloc.lower() in social_media_domains:
                continue  # Skip this URL
          #  print(url)
            path_segments = [s for s in parsed.path.split('/') if s]
            features = {
                'url': url,
                'scheme': parsed.scheme,
                'netloc': parsed.netloc,
                'path_segments': path_segments,
                'num_path_segments': len(path_segments),
                'has_articles_segment': 'articles' in path_segments,
                'last_segment': path_segments[-1] if path_segments else None
            }
            parsed_urls_features.append(features)
        # print(parsed_urls_features[:5])
        article_urls = rank_urls_for_articles([feature['url'] for feature in parsed_urls_features])
        # print(article_urls[:5])
        for url in article_urls[:1]:
            yield Request(url['url'], callback=self.parse_article, meta={'items': response.meta['items']})

    def parse_article(self, response):
      #  print(response.url)
        data = json.loads(extract(response.text, output_format="json"))

        branch = response.meta['items']['branch']
        country = response.meta['items']['country']
        topic = response.meta['items']['topic']
        image_url = response.meta['items']['image_url']
        # Determine which image URL to use
        if data.get('image'):
            image = response.urljoin(data.get('image'))
        else:
            image = image_url
            
        # Determine which description to use
        if data.get('excerpt') is None:
            description = data.get('raw_text')
        else:
            description = data.get('excerpt')
        DEBUG_MODE = True  # Set to False for production
    
        content = response.text
        if DEBUG_MODE and len(content) > 500:
            content = content[:500] + f"... [TRUNCATED - Total length: {len(response.text)}]"
        yield NewsItems(
            {
            'title': data.get('title'),
            'url': response.url,
            'image_url': image,
            'document_url': None,
            'created_at': data.get('date'),
            'description': description,
            'md': content,
            'collection_name': response.meta['items']['collection_name'],
            'branch': branch,
            'country': country,
            'topic': topic
            }
        )
