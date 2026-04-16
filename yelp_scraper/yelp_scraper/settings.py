import os

BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# Rendering strategy
#
# The course template uses local Playwright:
#
#   DOWNLOAD_HANDLERS = {
#       "http":  "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#       "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
#   }
#   PLAYWRIGHT_BROWSER_TYPE = "chromium"
#   PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30_000
#   PLAYWRIGHT_LAUNCH_OPTIONS = {"args": ["--disable-dev-shm-usage"]}
#
# Yelp blocks local headless Chromium with a DataDome 403/CAPTCHA on every
# request (verified — see attached logs).  Routing through the Zyte Smart
# Proxy did not help because Yelp detects browser-fingerprint signals
# regardless of IP.  The only approach that successfully returns content is
# the Zyte Data Extraction API with browserHtml=True, which runs a managed
# Playwright-based browser on Zyte's whitelisted infrastructure.
# All CSS/XPath selectors are identical to the Playwright version.
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
