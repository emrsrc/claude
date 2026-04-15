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
returns fully-rendered HTML.  Scroll actions were removed from detail page
requests after they caused 520 website-ban errors — Yelp detects the longer
browser session as automated activity.

Requires:
    scrapy-zyte-api  (pip install scrapy-zyte-api)
    ZYTE_API_KEY     set in settings.py or via env var

Run:
    scrapy crawl yelp
"""

import json
import re

import scrapy

from yelp_scraper.items import ReviewItem

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

# All pages use the same simple browser render.
# Scroll actions were removed from detail page requests — they triggered
# Zyte 520 "website-ban" errors because the extended browser session made
# the request detectable as automated.
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

    def __init__(self, debug="0", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._debug = int(debug)
        self._debug_saved = False

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
    # Parse a restaurant detail page → yield ReviewItems
    # RestaurantItem is no longer used; ReviewItem carries all fields.
    # Restaurants with no scraped reviews get one sentinel row with blank
    # reviewer_name / reviewer_rating / review_text.
    # ------------------------------------------------------------------
    def parse_restaurant(self, response):
        rd = response.meta["restaurant_data"]

        if self._debug and not self._debug_saved:
            import os
            os.makedirs("output", exist_ok=True)
            slug = re.sub(r"[^\w]", "_", rd.get("name", "restaurant"))[:30]
            path = f"output/debug_{slug}.html"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(response.text)
            self.logger.info(f"[DEBUG] Saved restaurant HTML → {path}")
            self._debug_saved = True

        # --- Try JSON-LD first (fastest, most structured) -------------
        json_ld_reviews = list(self._reviews_from_json_ld(response, rd))
        if json_ld_reviews:
            yield from json_ld_reviews
            return

        # --- Fall back to HTML parsing --------------------------------
        html_reviews = list(self._reviews_from_html(response, rd))
        if html_reviews:
            yield from html_reviews
            return

        # --- Sentinel row: restaurant with no scraped reviews ---------
        item = ReviewItem()
        item["restaurant_name"]         = rd.get("name", "")
        item["restaurant_rating"]       = rd.get("rating", "")
        item["restaurant_review_count"] = rd.get("review_count", "")
        item["restaurant_link"]         = rd.get("link", "")
        item["restaurant_location"]     = rd.get("location", "")
        item["restaurant_categories"]   = rd.get("categories", "")
        item["reviewer_name"]           = ""
        item["reviewer_rating"]         = ""
        item["review_text"]             = ""
        yield item

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
          1. Find every <a href="/biz/..."> that is a primary business name
             link (has visible text, not a utility link).
          2. Walk up to the enclosing <li> card to collect sibling data.
          3. De-duplicate by normalised URL.
        """
        cards = []
        seen = set()

        # Prefer heading-anchored links (most precise — Yelp puts business
        # names inside <h3>); fall back to any /biz/ anchor if none found.
        heading_anchors = response.css(
            'h3 a[href*="/biz/"]:not([href*="writeareview"])'
            ':not([href*="/photos"])'
        )
        all_biz_anchors = heading_anchors or response.css(
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
                "write a review", "order online", "order now", "order",
                "get directions", "get quote", "claimed", "unclaimed",
                "see all", "photos", "menu", "more info", "website",
                "call", "check in", "share", "add photo", "delivery",
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
        # Lead with Yelp's exact "Rated X.X stars" phrasing to avoid
        # matching unrelated star badge icons first
        for candidate in el.css("[aria-label]"):
            aria = candidate.attrib.get("aria-label", "")
            if re.search(r"rated\s+[\d.]+\s+star", aria, re.IGNORECASE):
                return _parse_rating(aria)
        # Wider fallback: any role=img or aria-label with digit + star
        for candidate in el.css("[role='img'], [aria-label*='star']"):
            aria = candidate.attrib.get("aria-label", "")
            if re.search(r"[\d.]+\s*star", aria, re.IGNORECASE):
                return _parse_rating(aria)
        return ""

    def _extract_review_count(self, el) -> str:
        # Case 1: digit + "review" in the same text node
        for text in el.css("::text").getall():
            m = re.search(r"([\d,]+)\s*review", text, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "")
        # Case 2: Yelp sometimes splits the count and the word "reviews"
        # across adjacent sibling text nodes
        all_texts = [t.strip() for t in el.css("::text").getall() if t.strip()]
        for i, text in enumerate(all_texts):
            if re.fullmatch(r"[\d,]+", text):
                neighbors = all_texts[max(0, i - 1):i] + all_texts[i + 1:i + 2]
                if any("review" in n.lower() for n in neighbors):
                    return text.replace(",", "")
        return ""

    def _extract_categories(self, el) -> str:
        cats = []
        # Yelp category links on search results use /search?find_desc=<Category>&find_loc=...
        # NOT /category/ — that was the old incorrect selector
        for a in el.css("a[href*='find_desc']"):
            text = a.css("::text").get("").strip()
            if text and text not in cats:
                cats.append(text)
        if not cats:
            # Fallback: plain <span> elements with no child links
            for span in el.css("span"):
                if span.css("a"):
                    continue
                text = span.css("::text").get("").strip()
                if text and len(text) < 40 and text not in cats:
                    if not re.fullmatch(r"[\d\s$.,·•\-]+", text):
                        cats.append(text)
        return ", ".join(cats)

    def _extract_location(self, el) -> str:
        # Priority 1: semantic class-based selectors
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

        # Priority 2: first <p> or <span> that looks like a location string.
        # Reject name containers, category containers, and any text that is
        # purely numeric/symbolic (ratings, review counts, price ranges).
        skip_labels = {
            "open", "closed", "sponsored", "new", "hot",
            "order online", "get directions", "see more",
            "open now", "temporarily closed",
        }
        for p in el.css("p, span"):
            if p.css("a[href*='/biz/'], a[href*='find_desc']"):
                continue                          # skip name + category containers
            joined = " ".join(p.css("::text").getall()).strip()
            if not joined or len(joined) > 120:
                continue
            if joined.lower() in skip_labels:
                continue
            # Skip pure numbers / rating values / review counts / price symbols
            if re.fullmatch(r"[\d\s$.,·•\-–—()\$]+", joined):
                continue
            if re.search(r"^\d+\.?\d*$", joined):          # e.g. "4.5"
                continue
            if re.search(r"[\d.]+\s*star|\breviews?\b|\brated\b", joined, re.IGNORECASE):
                continue
            # Must have at least one real alphabetic word (rules out "$$", "4.5", etc.)
            if not re.search(r"[a-zA-Z]{2,}", joined):
                continue
            return joined

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
                self.logger.debug(
                    f"JSON-LD @type={record.get('@type')} keys={list(record.keys())}"
                )
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
        item["restaurant_name"]         = rd.get("name", "")
        item["restaurant_rating"]       = rd.get("rating", "")
        item["restaurant_review_count"] = rd.get("review_count", "")
        item["restaurant_link"]         = rd.get("link", "")
        item["restaurant_location"]     = rd.get("location", "")
        item["restaurant_categories"]   = rd.get("categories", "")

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
        Identify review containers by three co-present signals:
          • a link to /user_details  (reviewer profile / avatar)
          • an aria-label containing "star"  (rating)
          • a <p lang="...">  (review text)

        Note: the reviewer name is NOT inside the <a href="/user_details">
        element — that anchor wraps only the avatar image.  The name lives
        in a sibling <span>, so we use XPath's following-sibling axis.
        """
        candidates = response.css(
            "li, section, article, [data-review-id], [id^='review_']"
        )

        yielded = 0
        for container in candidates:
            user_links = container.css(
                "a[href*='/user_details'], a[href*='/users/']"
            )
            star_els = container.css("[aria-label*='star']")
            text_els = container.css(
                "p[lang], p[lang] span, "
                "[class*='comment'] p, [class*='reviewText'] span, "
                "[class*='raw'] span, span[lang]"
            )

            # Require review text + at least one other signal
            if not text_els:
                continue
            if not (user_links or star_els):
                continue

            # --- Reviewer name ---
            # The name is in a sibling <span> of the avatar link, not inside it
            reviewer_name = ""
            if user_links:
                user_link = user_links[0]
                name_from_sibling = user_link.xpath(
                    "following-sibling::span[1]//text()"
                ).get("").strip()
                if name_from_sibling:
                    reviewer_name = name_from_sibling
                else:
                    # Walk up to shared wrapper, grab first span without
                    # star/rating/date noise
                    wrapper = user_link.xpath("parent::*[1]")
                    for span in wrapper.css("span"):
                        candidate = " ".join(span.css("::text").getall()).strip()
                        if candidate and not re.search(
                            r"star|rating|\d+/\d+|review|photo", candidate, re.IGNORECASE
                        ):
                            reviewer_name = candidate
                            break
                if not reviewer_name:
                    reviewer_name = (
                        user_link.attrib.get("aria-label", "").strip()
                        or user_link.attrib.get("title", "").strip()
                    )

            # --- Reviewer rating ---
            aria = star_els.attrib.get("aria-label", "")
            reviewer_rating = _parse_rating(aria)

            # --- Review text ---
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
            item["restaurant_name"]         = rd.get("name", "")
            item["restaurant_rating"]       = rd.get("rating", "")
            item["restaurant_review_count"] = rd.get("review_count", "")
            item["restaurant_link"]         = rd.get("link", "")
            item["restaurant_location"]     = rd.get("location", "")
            item["restaurant_categories"]   = rd.get("categories", "")
            item["reviewer_name"]           = reviewer_name
            item["reviewer_rating"]         = reviewer_rating
            item["review_text"]             = review_text[:3000]
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
