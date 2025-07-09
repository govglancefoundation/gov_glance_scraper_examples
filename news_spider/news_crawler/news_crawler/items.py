# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NewsCrawlerItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class NewsItems(scrapy.Item):
    title = scrapy.Field()
    url = scrapy.Field()
    image_url = scrapy.Field()
    document_url = scrapy.Field()
    created_at = scrapy.Field()
    description = scrapy.Field()
    md = scrapy.Field()
    collection_name = scrapy.Field()
    topic = scrapy.Field()
    branch = scrapy.Field()
    country = scrapy.Field()

class NotificationModel(scrapy.Item):
    title = scrapy.Field()
    table_id = scrapy.Field()
    country_schema = scrapy.Field()
    table_source_name = scrapy.Field()
    image_url = scrapy.Field() 
    description = scrapy.Field()    
    topic = scrapy.Field()  
    notification = scrapy.Field()
    collection_name = scrapy.Field()