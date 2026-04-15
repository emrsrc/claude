BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# Playwright download handlers – required for JS rendering
# ---------------------------------------------------------------------------
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Playwright requires the asyncio reactor
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ],
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000  # ms

# ---------------------------------------------------------------------------
# Browser-like headers to reduce bot-detection fingerprinting
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# ---------------------------------------------------------------------------
# Crawl politeness
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False          # Yelp disallows scrapers; skip for coursework
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 3              # base delay between requests (seconds)
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 3
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]
HTTPERROR_ALLOWED_CODES = [403, 404]  # log but don't crash on blocks

# ---------------------------------------------------------------------------
# Item pipelines
# ---------------------------------------------------------------------------
ITEM_PIPELINES = {
    "yelp_scraper.pipelines.CsvExportPipeline": 300,
}

# ---------------------------------------------------------------------------
# Feed exports (one CSV per item type)
# ---------------------------------------------------------------------------
FEEDS = {
    "output/restaurants.csv": {
        "format": "csv",
        "item_classes": ["yelp_scraper.items.RestaurantItem"],
        "overwrite": True,
    },
    "output/reviews.csv": {
        "format": "csv",
        "item_classes": ["yelp_scraper.items.ReviewItem"],
        "overwrite": True,
    },
}

FEED_EXPORT_ENCODING = "utf-8"

# ---------------------------------------------------------------------------
# Optional: Zyte Smart Proxy (uncomment and fill in your API key if blocked)
# ---------------------------------------------------------------------------
# pip install scrapy-zyte-smartproxy
#
# ZYTE_SMARTPROXY_ENABLED = True
# ZYTE_SMARTPROXY_APIKEY = "YOUR_ZYTE_API_KEY"
# DOWNLOADER_MIDDLEWARES = {
#     "scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware": 610,
# }
#
# Or, for Zyte API transparent mode:
# pip install scrapy-zyte-api
#
# ZYTE_API_KEY = "YOUR_ZYTE_API_KEY"
# ZYTE_API_TRANSPARENT_MODE = True
# DOWNLOADER_MIDDLEWARES = {
#     "scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware": 1000,
# }
# SPIDER_MIDDLEWARES = {
#     "scrapy_zyte_api.ScrapyZyteAPISpiderMiddleware": 100,
# }
