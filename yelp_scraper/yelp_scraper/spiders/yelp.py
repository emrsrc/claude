"""
yelp.py
-------
Scrapy spider that scrapes 20 pages of Yelp restaurant search results for
Indianapolis, IN, then follows each restaurant link to collect first-page
reviews.

Requires:
    scrapy-playwright  (pip install scrapy-playwright)
    playwright         (playwright install chromium)

Run:
    scrapy crawl yelp
"""

import json
import re

import scrapy
from scrapy_playwright.page import PageMethod

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
                    "playwright": True,
                    "playwright_include_response": True,
                    "playwright_page_methods": [
                        # Wait for the DOM to settle
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        # Give React time to hydrate
                        PageMethod("wait_for_timeout", 4000),
                        # Scroll halfway to trigger lazy-loaded cards
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        # Scroll to bottom for remaining cards
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
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
                    "playwright": True,
                    "playwright_include_response": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("wait_for_timeout", 4000),
                        # Scroll to load reviews
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
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
          1. Find every <a href="/biz/..."> link that looks like a primary
             business name link (has visible text, is not a utility link).
          2. Walk up the DOM via parent selectors to collect sibling data
             (rating, review count, categories, location) from the same card.
          3. De-duplicate by normalised URL.
        """
        cards = []
        seen = set()

        # ---- Step 1: locate all business-name anchor elements --------
        # Primary business links use /biz/<slug> paths.
        # We exclude links to write-a-review, photos, etc.
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

            # Skip empty names, very short strings, or UI labels
            if not name or len(name) < 3:
                continue
            skip_words = {
                "write a review", "order online", "get directions",
                "claimed", "unclaimed", "see all", "photos",
            }
            if name.lower() in skip_words:
                continue

            # Normalise URL
            if href.startswith("/"):
                full_url = "https://www.yelp.com" + href
            else:
                full_url = href
            clean_url = full_url.split("?")[0]

            if clean_url in seen:
                continue
            seen.add(clean_url)

            # ---- Step 2: find the enclosing card container -----------
            # Walk up several levels to find the list-item / card div
            # that contains rating, review count, categories, location.
            #
            # Yelp nests content roughly as:
            #   <ul class="...">
            #     <li>
            #       ...card content including the <a href="/biz/...">...
            #     </li>
            #   </ul>
            #
            # XPath: ancestor::li[1] gives us the nearest <li> ancestor.
            card_el = anchor.xpath("ancestor::li[1]")
            if not card_el:
                # Some results are in <div> containers rather than <li>
                card_el = anchor.xpath("ancestor::div[contains(@class,'container')][1]")
            if not card_el:
                card_el = anchor  # last resort: use the anchor itself

            rating = self._extract_rating(card_el)
            review_count = self._extract_review_count(card_el)
            categories = self._extract_categories(card_el)
            location = self._extract_location(card_el)

            cards.append(
                {
                    "name": name,
                    "link": clean_url,
                    "rating": rating,
                    "review_count": review_count,
                    "categories": categories,
                    "location": location,
                    "page_number": response.meta.get("page_number", ""),
                }
            )

        return cards

    # ------------------------------------------------------------------
    # Field-level extractors (work on an element / selector)
    # ------------------------------------------------------------------

    def _extract_rating(self, el) -> str:
        # aria-label="Rated X stars" or "X star rating"
        rating_el = el.css("[aria-label*='star rating'], [aria-label*='star']")
        if rating_el:
            return _parse_rating(rating_el.attrib.get("aria-label", ""))

        # role="img" with aria-label describing the rating
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
        # Category links point to Yelp category search URLs
        for a in el.css("a[href*='category']"):
            text = a.css("::text").get("").strip()
            if text and text not in cats:
                cats.append(text)
        # Fallback: spans/buttons styled as category pills
        if not cats:
            for span in el.css("span[class*='tag'], button[class*='tag']"):
                text = span.css("::text").get("").strip()
                if text and text not in cats:
                    cats.append(text)
        return ", ".join(cats)

    def _extract_location(self, el) -> str:
        # Explicit address / neighbourhood elements
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

        # Heuristic: short text that looks like a neighbourhood name or
        # street address but is not a rating / review snippet
        for text in el.css("::text").getall():
            text = text.strip()
            if not text or len(text) > 80:
                continue
            # Street address pattern (starts with digits)
            if re.match(r"^\d+\s+\w", text):
                return text
            # Neighbourhood: Title Case, 2–4 words, no digits
            if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}$", text):
                # Exclude obvious non-location words
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

            # data can be a single object or a list
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
                    yield self._build_review_item(rev, rd, source="json-ld")
                if reviews:
                    return  # stop after first matching record

    def _build_review_item(self, rev_data: dict, rd: dict, source: str) -> ReviewItem:
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
        Yelp renders reviews as a list of <li> elements.  Because class names
        are obfuscated and change frequently, we identify review containers
        by the co-presence of three semantic signals:
          • a link to /user_details (reviewer profile)
          • an element with aria-label containing "star" (rating)
          • a <p> element with a lang attribute (review text)
        """
        # Candidate containers to search within
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

            # --- Reviewer name ---
            reviewer_name = user_links.css("::text").get("").strip()
            if not reviewer_name:
                reviewer_name = (
                    user_links.attrib.get("aria-label", "").strip()
                    or user_links.attrib.get("title", "").strip()
                )

            # --- Reviewer rating ---
            aria = star_els.attrib.get("aria-label", "")
            reviewer_rating = _parse_rating(aria)

            # --- Review text ---
            texts = text_els.css("::text").getall()
            review_text = " ".join(t.strip() for t in texts if t.strip())

            if not review_text:
                # Try plain <p> children as last resort
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
            item["review_text"] = review_text[:3000]  # cap length
            yield item
            yielded += 1

        if not yielded:
            self.logger.debug(
                f"No HTML reviews found for: {rd.get('name')} — "
                f"page may require further interaction or uses a different layout."
            )

    # ------------------------------------------------------------------
    # Error callback
    # ------------------------------------------------------------------
    def errback(self, failure):
        self.logger.error(
            f"Request failed [{failure.value.__class__.__name__}]: "
            f"{failure.request.url}"
        )
