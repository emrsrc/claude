import os

BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

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
# ---------------------------------------------------------------------------
ZYTE_API_KEY = os.environ.get("ZYTE_API_KEY", "d5ade7ca66f54281b9788b32c08900c9")

DOWNLOAD_HANDLERS = {
    "http":  "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
    "https": "scrapy_zyte_api.ScrapyZyteAPIDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPIDownloaderMiddleware": 1000,
}

SPIDER_MIDDLEWARES = {
    "scrapy_zyte_api.ScrapyZyteAPISpiderMiddleware": 100,
}

# Reuse the same Zyte-managed browser session (same IP + cookies) across
# all requests to yelp.com.  This makes listing→detail navigation look like
# a single real user rather than isolated requests, which significantly
# reduces 520 website-ban errors on /biz/ pages.
ZYTE_API_SESSION_ENABLED = True
ZYTE_API_SESSION_PARAMS = {"browserHtml": True}

# ---------------------------------------------------------------------------
# Crawl politeness
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 15
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

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
# Feed exports
# ---------------------------------------------------------------------------
FEEDS = {
    "output/yelp_data.csv": {
        "format": "csv",
        "overwrite": True,
    },
}

FEED_EXPORT_ENCODING = "utf-8"
