# Government News Spider Collection

A Scrapy-based web crawler designed to systematically collect news articles from government websites across multiple countries, with specialized heuristics for identifying high-quality article content.

## Overview

This spider collection focuses on crawling government websites to extract news articles, press releases, and official announcements. The system uses advanced URL ranking algorithms and content extraction techniques to identify and process legitimate news content while filtering out navigational and administrative pages.

## Architecture

### Core Components

- **Spiders**: Country-specific crawlers (`united_states_gov_news.py`, `australia_gov_news.py`)
- **Items**: Data models defining the structure of scraped content (`items.py`)
- **Pipelines**: Data processing and cleaning logic (`pipelines.py`)
- **Middlewares**: Request/response processing and proxy management (`middlewares.py`)
- **Settings**: Configuration for crawling behavior and API keys (`settings.py`)

## Key Libraries and Technologies

### Content Extraction

- **Trafilatura**: Primary library for extracting clean article content from HTML
- **BeautifulSoup**: HTML parsing and DOM manipulation for preprocessing
- **Readability**: Article content extraction using readability algorithms
- **Markdownify**: Converting HTML content to Markdown format

### Web Scraping Infrastructure

- **Scrapy**: Core web crawling framework
- **Zyte API**: Premium proxy service for handling blocked requests
- **Firecrawl**: Alternative content extraction service for JavaScript-heavy sites
- **LinkExtractor**: Scrapy's built-in link discovery mechanism

### Data Processing

- **dateutil**: Intelligent date parsing and timezone handling
- **pytz**: Timezone conversion utilities
- **itemadapter**: Scrapy item processing interface

## URL Ranking Heuristics

The spider employs sophisticated heuristics to identify article URLs from general government pages:

### Positive Indicators (Increase Article Likelihood)

- **Date patterns**: `/YYYY/MM/DD/` (+5 points), `/YYYY-MM-DD/` (+5 points)
- **Content type segments**: `article` (+4), `news` (+3), `press-release` (+3), `speech` (+3)
- **Document types**: `report` (+3), `publication` (+2), `document` (+2)
- **Government-specific**: `announcement` (+3), `statement` (+3), `advisory` (+3)
- **Descriptive slugs**: Long hyphenated URLs (+1-3 points based on length)

### Negative Indicators (Decrease Article Likelihood)

- **Navigation elements**: `category` (-3), `archive` (-2), `search` (-3)
- **Administrative pages**: `admin` (-5), `login` (-5), `dashboard` (-4)
- **Site structure**: `sitemap` (-2), `feed` (-1), `json` (-1)
- **Pagination**: `/page/` (-2)

### Scoring System

- **Minimum threshold**: 5 points required for URL consideration
- **Path segment analysis**: Bonus for appropriate URL depth (2+ segments)
- **Domain bonuses**: `.gov` (+1), `.edu` (+1), `.org` (+0.5)

## Data Structure

### Source Configuration (JSON Files)

Each source is defined in JSON configuration files (`united_states.json`, `australia_data.json`) with the following structure:

```json
{
  "collection_name": "Human-readable source name",
  "source_url": "https://example.gov/news",
  "table_name": "article_objects",
  "title": "Display title for the source",
  "topic": "Content category (e.g., 'State Government')",
  "image_url": "Default image URL or null",
  "country": "Country of origin",
  "branch": "Government branch (Executive, Legislative, Judicial)"
}
```

### Output Data Model

Each scraped article produces a `NewsItems` object containing:

```python
{
    'title': str,           # Article headline
    'url': str,            # Canonical article URL
    'image_url': str,      # Featured image URL
    'document_url': str,   # Link to associated document (if any)
    'created_at': datetime, # Publication date
    'description': str,    # Article excerpt or summary
    'md': str,            # Full article content in Markdown
    'collection_name': str, # Source identifier
    'branch': str,         # Government branch
    'country': str,        # Country of origin
    'topic': str          # Content category
}
```

## Database Integration

### Workflow

1. **Source Management**: JSON configuration files define crawling targets
2. **URL Discovery**: Spiders visit source URLs and extract all internal links
3. **Content Ranking**: URLs are scored using heuristic algorithms
4. **Article Extraction**: High-scoring URLs are processed for content
5. **Data Storage**: Cleaned articles are stored in PostgreSQL database

### Database Schema

The crawler populates the `article_objects` table with standardized news article data. Each record includes:

- Content metadata (title, URL, publication date)
- Source attribution (collection name, government branch, country)
- Full article content in both HTML and Markdown formats
- Associated media (images, documents)

## Middleware Features

### Anti-Blocking Measures

- **ZyteProxyFallbackMiddleware**: Automatic proxy switching on request blocks
- **AutoHeadersMiddleware**: Randomized browser headers to avoid detection
- **User-Agent Rotation**: Multiple browser signatures for request diversity

### Request Processing

- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Rate Limiting**: Respectful crawling with configurable delays
- **Compression**: Automatic response compression handling

## Configuration

### Environment Variables

```bash
POSTGRES_ADDRESS=your_db_host
POSTGRES_USERNAME=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DBNAME=your_db_name
ZYTE_API_KEY=your_proxy_key
FIRE_CRAWL_API_KEY=your_firecrawl_key
```

### Crawling Parameters

- **CONCURRENT_REQUESTS**: 16 (adjustable based on server capacity)
- **DOWNLOAD_DELAY**: 4-5 seconds between requests
- **RETRY_TIMES**: 4 attempts for failed requests
- **AUTOTHROTTLE**: Enabled for adaptive rate limiting

## Usage

### Running Individual Spiders

```bash
# Crawl US government sources
scrapy crawl united_states_gov_news

# Crawl Australian government sources
scrapy crawl australia_gov_news
```

### Adding New Sources

1. Add source configuration to appropriate JSON file
2. Ensure source URL contains discoverable article links
3. Test URL ranking algorithm performance
4. Monitor crawling logs for extraction quality

## Content Processing Pipeline

### Text Cleaning

- **HTML Tag Removal**: Strip formatting while preserving content structure
- **Script Elimination**: Remove JavaScript and style blocks
- **Entity Decoding**: Convert HTML entities to readable text
- **Whitespace Normalization**: Standardize spacing and line breaks

### Date Processing

- **Timezone Conversion**: All dates normalized to UTC
- **Format Standardization**: Consistent datetime objects across sources
- **Parsing Flexibility**: Handles various government date formats

### Content Extraction

- **Readability Algorithm**: Identifies main article content
- **Markdown Conversion**: Preserves formatting in portable format
- **Image Processing**: Resolves relative URLs to absolute paths
- **Metadata Extraction**: Captures publication dates and excerpts

## Quality Assurance

### URL Filtering

- **Social Media Exclusion**: Filters out social platform links
- **Domain Validation**: Ensures government domain requirements
- **Duplicate Prevention**: Avoids processing identical URLs

### Content Validation

- **Minimum Content Length**: Ensures substantial article content
- **Date Validation**: Confirms reasonable publication dates
- **Title Extraction**: Validates article headline presence

This crawler system provides a robust foundation for systematically collecting and processing government news content across multiple countries and jurisdictions.
