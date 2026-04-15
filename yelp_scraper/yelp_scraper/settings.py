import os

BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# Zyte API key
# Override at run-time via:  export ZYTE_API_KEY=<your-key>
# ---------------------------------------------------------------------------
ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY", "d5ade7ca66f54281b9788b32c08900c9")

_ZYTE_PROXY = {
    "server": "http://proxy.zyte.com:8011",
    "username": ZYTE_API_KEY,
    "password": "",
}

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

# Launch options: headless Chromium routed through Zyte proxy
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "proxy": _ZYTE_PROXY,          # all browser-level HTTP/S goes via Zyte
    "args": [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ],
}

# Browser context: ignore TLS errors caused by Zyte's SSL inspection
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "ignore_https_errors": True,
    }
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
# (Zyte rotates IPs, so we can afford slightly higher concurrency)
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False          # Yelp disallows scrapers; skip for coursework
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 2              # base delay between requests (seconds)
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 20
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

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
