import os

BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# Zyte API – browser-rendered HTML (replaces local Playwright + raw proxy)
# Override at run-time:  export ZYTE_API_KEY=<your-key>
# ---------------------------------------------------------------------------
ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY", "d5ade7ca66f54281b9788b32c08900c9")

# ---------------------------------------------------------------------------
# Download handlers
#
# Course baseline – standard Playwright (local Chromium, no proxy):
#
#   DOWNLOAD_HANDLERS = {
#       "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#       "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#   }
#   PLAYWRIGHT_BROWSER_TYPE = "chromium"
#   PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
#
# Active configuration – Zyte API browser rendering:
# Yelp returns 503 when a local Playwright browser is routed through a raw
# proxy.  Zyte API's browserHtml option runs a managed browser on Zyte's
# infrastructure and returns fully-rendered HTML, which Yelp allows.
# The spider meta uses  "zyte_api": {"browserHtml": True}  instead of the
# Playwright equivalents; all CSS/XPath parsing is otherwise identical.
# ---------------------------------------------------------------------------
DOWNLOAD_HANDLERS = {
    "http": "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
    "https": "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
}

# Both Playwright and Zyte API require the asyncio reactor
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware": 1000,
}

SPIDER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPISpiderMiddleware": 100,
}

# ---------------------------------------------------------------------------
# Crawl politeness
# (Zyte API manages its own concurrency on their end, but we still throttle
#  to avoid burning through quota too fast)
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]
HTTPERROR_ALLOWED_CODES = [403, 404]

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
