BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# Playwright integration (course requirement)
# ---------------------------------------------------------------------------
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30_000  # ms

PLAYWRIGHT_LAUNCH_OPTIONS = {
    # headless true by default; set False for local debugging
    "args": [
        "--disable-dev-shm-usage",
        "--no-sandbox",              # required in many Linux/server environments
    ],
}

# Route Playwright's Chromium through Zyte Smart Proxy so requests come from
# residential/rotating IPs that Yelp does not block.
# ignore_https_errors is required because the proxy performs SSL interception.
ZYTE_API_KEY = "d5ade7ca66f54281b9788b32c08900c9"
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "proxy": {
            "server": "http://proxy.zyte.com:8011",
            "username": "d5ade7ca66f54281b9788b32c08900c9",
            "password": "",
        },
        "ignore_https_errors": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1280, "height": 800},
        "locale": "en-US",
    }
}

# ---------------------------------------------------------------------------
# Crawl politeness
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2
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
# Feed exports
# ---------------------------------------------------------------------------
FEEDS = {
    "output/yelp_data.csv": {
        "format": "csv",
        "overwrite": True,
    },
}

FEED_EXPORT_ENCODING = "utf-8"
