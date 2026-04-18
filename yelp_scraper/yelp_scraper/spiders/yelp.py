"""
yelp.py
-------
Scrapy spider that scrapes 20 pages of Yelp restaurant search results for
Indianapolis, IN, then follows each restaurant link to collect first-page
reviews.

Rendering strategy
------------------
All pages are fetched via the Zyte API with ``browserHtml: true``.  Zyte
runs a real managed browser on its end, executes the page JavaScript, and
returns fully-rendered HTML – the same approach confirmed working in the
Zyte API playground.  This avoids the 503 / CAPTCHA issues that arise when
routing a local Playwright browser through Zyte's raw proxy.

Requires:
    scrapy-zyte-api  (pip install scrapy-zyte-api)
    ZYTE_API_KEY     set in settings.py or via env var

Run:
    scrapy crawl yelp
"""

import json
import re

import scrapy

from yelp_scraper.items import RestaurantItem, ReviewItem

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = (
    "https://www.yelp.com/search"
    "?find_desc=Restaurants"
    "&find_loc=Indianapolis%2C+IN"
)
TOTAL_PAGES = 20
RESULTS_PER_PAGE = 10  # Yelp shows 10 results per listing page

# Zyte API request params shared by every request
_ZYTE_BROWSER = {
    "browserHtml": True,
}


# ---------------------------------------------------------------------------
# Helper: extract star rating value from an aria-label string
# ---------------------------------------------------------------------------
def _parse_rating(aria_label: str) -> str:
    """Return e.g. '4.5' from 'Rated 4.5 stars' or '4 star rating'."""
    m = re.search(r"([\d.]+)\s*star", aria_label, re.IGNORECASE)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Spider
# ---------------------------------------------------------------------------
class YelpSpider(scrapy.Spider):
    name = "yelp"

    # ------------------------------------------------------------------
    # Start requests – one per listing page (20 pages × 10 results = 200)
    # ------------------------------------------------------------------
    def start_requests(self):
        for page in range(TOTAL_PAGES):
            offset = page * RESULTS_PER_PAGE
            url = f"{BASE_URL}&start={offset}"
            yield scrapy.Request(
                url=url,
                callback=self.parse_listing,
                errback=self.errback,
                meta={
                    "zyte_api": _ZYTE_BROWSER,
                    "page_number": page + 1,
                },
            )

    # ------------------------------------------------------------------
    # Parse a listing page → yield requests to each restaurant detail page
    # ------------------------------------------------------------------
    def parse_listing(self, response):
        page_number = response.meta["page_number"]

        cards = self._extract_cards(response)
        self.logger.info(
            f"Listing page {page_number}: found {len(cards)} restaurant cards"
        )

        if not cards:
            self.logger.warning(
                f"Page {page_number}: no cards found – possible CAPTCHA or "
                f"layout change. URL: {response.url}"
            )

        for card in cards:
            if not card.get("name") or not card.get("link"):
                continue
            yield scrapy.Request(
                url=card["link"],
                callback=self.parse_restaurant,
                errback=self.errback,
                meta={
                    "zyte_api": _ZYTE_BROWSER,
                    "restaurant_data": card,
                },
            )

    # ------------------------------------------------------------------
    # Parse a restaurant detail page → yield RestaurantItem + ReviewItems
    # ------------------------------------------------------------------
    def parse_restaurant(self, response):
        rd = response.meta["restaurant_data"]

        # --- Yield the restaurant summary row -------------------------
        item = RestaurantItem()
        item["name"] = rd.get("name", "")
        item["rating"] = rd.get("rating", "")
        item["review_count"] = rd.get("review_count", "")
        item["link"] = rd.get("link", "")
        item["location"] = rd.get("location", "")
        item["categories"] = rd.get("categories", "")
        item["page_number"] = rd.get("page_number", "")
        yield item

        # --- Try JSON-LD first (fastest, most structured) -------------
        json_ld_reviews = list(self._reviews_from_json_ld(response, rd))
        if json_ld_reviews:
            yield from json_ld_reviews
            return

        # --- Fall back to HTML parsing --------------------------------
        yield from self._reviews_from_html(response, rd)

    # ==================================================================
    # Private helpers
    # ==================================================================

    # ------------------------------------------------------------------
    # Card extraction from listing page
    # ------------------------------------------------------------------
    def _extract_cards(self, response):
        """
        Extract restaurant summary dicts from a listing-page response.

        Strategy:
          1. Find every <a href="/biz/..."> link that is a primary business
             name link (has visible text, is not a utility link).
          2. Walk up to the enclosing <li> to collect sibling data
             (rating, review count, categories, location) from the same card.
          3. De-duplicate by normalised URL.
        """
        cards = []
        seen = set()

        all_biz_anchors = response.css(
            'a[href*="/biz/"]:not([href*="writeareview"])'
            ':not([href*="/photos"])'
            ':not([href*="/menu"])'
        )

        for anchor in all_biz_anchors:
            href = anchor.attrib.get("href", "")
            name = " ".join(anchor.css("::text").getall()).strip()

            # Remove numeric rank prefix ("1. ", "2. ", etc.)
            name = re.sub(r"^\d+\.\s*", "", name).strip()

            if not name or len(name) < 3:
                continue
            skip_words = {
                "write a review", "order online", "get directions",
                "claimed", "unclaimed", "see all", "photos",
            }
            if name.lower() in skip_words:
                continue

            if href.startswith("/"):
                full_url = "https://www.yelp.com" + href
            else:
                full_url = href
            clean_url = full_url.split("?")[0]

            if clean_url in seen:
                continue
            seen.add(clean_url)

            # Walk up to the nearest enclosing <li> card element
            card_el = anchor.xpath("ancestor::li[1]")
            if not card_el:
                card_el = anchor.xpath(
                    "ancestor::div[contains(@class,'container')][1]"
                )
            if not card_el:
                card_el = anchor

            cards.append(
                {
                    "name": name,
                    "link": clean_url,
                    "rating": self._extract_rating(card_el),
                    "review_count": self._extract_review_count(card_el),
                    "categories": self._extract_categories(card_el),
                    "location": self._extract_location(card_el),
                    "page_number": response.meta.get("page_number", ""),
                }
            )

        return cards

    # ------------------------------------------------------------------
    # Field-level extractors
    # ------------------------------------------------------------------

    def _extract_rating(self, el) -> str:
        rating_el = el.css("[aria-label*='star rating'], [aria-label*='star']")
        if rating_el:
            return _parse_rating(rating_el.attrib.get("aria-label", ""))
        for candidate in el.css("[role='img']"):
            aria = candidate.attrib.get("aria-label", "")
            if "star" in aria.lower():
                return _parse_rating(aria)
        return ""

    def _extract_review_count(self, el) -> str:
        for text in el.css("::text").getall():
            m = re.search(r"([\d,]+)\s*review", text, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "")
        return ""

    def _extract_categories(self, el) -> str:
        cats = []
        for a in el.css("a[href*='category']"):
            text = a.css("::text").get("").strip()
            if text and text not in cats:
                cats.append(text)
        if not cats:
            for span in el.css("span[class*='tag'], button[class*='tag']"):
                text = span.css("::text").get("").strip()
                if text and text not in cats:
                    cats.append(text)
        return ", ".join(cats)

    def _extract_location(self, el) -> str:
        for selector in [
            "[class*='secondaryAttributes'] ::text",
            "address ::text",
            "[class*='neighborhood'] ::text",
            "[class*='address'] ::text",
        ]:
            texts = el.css(selector).getall()
            joined = " ".join(t.strip() for t in texts if t.strip())
            if joined:
                return joined

        for text in el.css("::text").getall():
            text = text.strip()
            if not text or len(text) > 80:
                continue
            if re.match(r"^\d+\s+\w", text):
                return text
            if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}$", text):
                skip = {"Open", "Closed", "Sponsored", "New", "Hot"}
                if text not in skip:
                    return text
        return ""

    # ------------------------------------------------------------------
    # Review extraction from JSON-LD structured data
    # ------------------------------------------------------------------
    def _reviews_from_json_ld(self, response, rd):
        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            records = data if isinstance(data, list) else [data]
            for record in records:
                biz_type = record.get("@type", "")
                if biz_type not in (
                    "Restaurant", "FoodEstablishment", "LocalBusiness", "BarOrPub",
                ):
                    continue
                reviews = record.get("review", [])
                if isinstance(reviews, dict):
                    reviews = [reviews]
                for rev in reviews:
                    yield self._build_review_item(rev, rd)
                if reviews:
                    return

    def _build_review_item(self, rev_data: dict, rd: dict) -> ReviewItem:
        item = ReviewItem()
        item["restaurant_name"] = rd.get("name", "")
        item["restaurant_rating"] = rd.get("rating", "")
        item["restaurant_review_count"] = rd.get("review_count", "")
        item["restaurant_link"] = rd.get("link", "")
        item["restaurant_location"] = rd.get("location", "")
        item["restaurant_categories"] = rd.get("categories", "")

        author = rev_data.get("author", {})
        item["reviewer_name"] = (
            author.get("name", "") if isinstance(author, dict) else str(author)
        )

        rating_info = rev_data.get("reviewRating", {})
        item["reviewer_rating"] = (
            str(rating_info.get("ratingValue", ""))
            if isinstance(rating_info, dict)
            else ""
        )

        item["review_text"] = rev_data.get(
            "reviewBody", rev_data.get("description", "")
        )
        return item

    # ------------------------------------------------------------------
    # Review extraction from rendered HTML
    # ------------------------------------------------------------------
    def _reviews_from_html(self, response, rd):
        """
        Identify review containers by the co-presence of three signals:
          • a link to /user_details  (reviewer profile)
          • aria-label containing "star"  (rating)
          • a <p lang="...">  (review text)
        """
        candidates = response.css(
            "li, section, article, [data-review-id], [id^='review_']"
        )

        yielded = 0
        for container in candidates:
            user_links = container.css("a[href*='/user_details']")
            star_els = container.css(
                "[aria-label*='star rating'], [aria-label*='star']"
            )
            text_els = container.css("p[lang], p[lang] span")

            if not (user_links and star_els and text_els):
                continue

            reviewer_name = user_links.css("::text").get("").strip()
            if not reviewer_name:
                reviewer_name = (
                    user_links.attrib.get("aria-label", "").strip()
                    or user_links.attrib.get("title", "").strip()
                )

            aria = star_els.attrib.get("aria-label", "")
            reviewer_rating = _parse_rating(aria)

            texts = text_els.css("::text").getall()
            review_text = " ".join(t.strip() for t in texts if t.strip())
            if not review_text:
                review_text = " ".join(
                    t.strip()
                    for t in container.css("p::text").getall()
                    if t.strip()
                )

            if not (reviewer_name or review_text):
                continue

            item = ReviewItem()
            item["restaurant_name"] = rd.get("name", "")
            item["restaurant_rating"] = rd.get("rating", "")
            item["restaurant_review_count"] = rd.get("review_count", "")
            item["restaurant_link"] = rd.get("link", "")
            item["restaurant_location"] = rd.get("location", "")
            item["restaurant_categories"] = rd.get("categories", "")
            item["reviewer_name"] = reviewer_name
            item["reviewer_rating"] = reviewer_rating
            item["review_text"] = review_text[:3000]
            yield item
            yielded += 1

        if not yielded:
            self.logger.debug(
                f"No HTML reviews found for: {rd.get('name')} – "
                f"JSON-LD had no reviews and HTML structure unrecognised."
            )

    # ------------------------------------------------------------------
    # Error callback
    # ------------------------------------------------------------------
    def errback(self, failure):
        self.logger.error(
            f"Request failed [{failure.value.__class__.__name__}]: "
            f"{failure.request.url}"
        )
