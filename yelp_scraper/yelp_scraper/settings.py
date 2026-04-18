import os

BOT_NAME = "yelp_scraper"

SPIDER_MODULES = ["yelp_scraper.spiders"]
NEWSPIDER_MODULE = "yelp_scraper.spiders"

# ---------------------------------------------------------------------------
# User-agent — a real-browser UA helps reduce first-request flags
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)

# ---------------------------------------------------------------------------
# Playwright + Zyte Smart Proxy integration
#
# Architecture:
#   scrapy-playwright   → download handler (local Chromium, course requirement)
#   scrapy-zyte-smartproxy → downloader middleware (routes non-browser traffic)
#   Playwright launch proxy → routes browser traffic through Zyte Smart Proxy
#
# Both layers use the same ZYTE_API_KEY.  Yelp's DataDome protection can
# sometimes still fingerprint headless Chromium even behind a proxy; if a
# request gets blocked, scrapy-playwright will retry it automatically via
# RETRY_HTTP_CODES below.
# ---------------------------------------------------------------------------

# Pull key from env (fall back to committed value for the class submission).
ZYTE_API_KEY = os.environ.get(
    "ZYTE_API_KEY", "d5ade7ca66f54281b9788b32c08900c9"
)
ZYTE_SMARTPROXY_APIKEY = ZYTE_API_KEY
ZYTE_SMARTPROXY_URL = "http://proxy.zyte.com:8011"

# --- Scrapy-Playwright download handlers -----------------------------------
DOWNLOAD_HANDLERS = {
    "http":  "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Playwright requires the asyncio reactor
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000  # ms

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ],
    # Route every page-load through Zyte Smart Proxy.  The proxy terminates
    # TLS, rotates IPs, and replays the request from a clean residential IP
    # which dramatically reduces DataDome 403/CAPTCHA responses.
    "proxy": {
        "server":   ZYTE_SMARTPROXY_URL,
        "username": ZYTE_API_KEY,
        "password": "",
    },
}

# Single default context — the proxy is configured at launch level above so
# every new context inherits it.
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "ignore_https_errors": True,  # Zyte uses its own TLS cert
        "viewport": {"width": 1366, "height": 900},
    },
}

# --- Zyte Smart Proxy downloader middleware --------------------------------
# Handles any non-Playwright request (e.g. robots.txt if enabled) through
# the same proxy credentials.
DOWNLOADER_MIDDLEWARES = {
    "scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware": 610,
}

# ---------------------------------------------------------------------------
# Crawl politeness
# ---------------------------------------------------------------------------
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [403, 429, 500, 502, 503, 504, 520, 522]
HTTPERROR_ALLOWED_CODES = [404]

# ---------------------------------------------------------------------------
# Item pipelines
# ---------------------------------------------------------------------------
ITEM_PIPELINES = {
    "yelp_scraper.pipelines.CsvExportPipeline": 300,
}

# ---------------------------------------------------------------------------
# Feed exports — single consolidated CSV
# ---------------------------------------------------------------------------
FEEDS = {
    "output/yelp_data.csv": {
        "format": "csv",
        "overwrite": True,
    },
}

FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"
