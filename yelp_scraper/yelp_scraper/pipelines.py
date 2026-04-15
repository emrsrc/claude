from itemadapter import ItemAdapter
from yelp_scraper.items import RestaurantItem, ReviewItem


class CsvExportPipeline:
    """
    Pass-through pipeline.  Actual CSV writing is handled by Scrapy's
    built-in FEEDS setting (see settings.py).  This class is kept for
    any future per-item validation or cleaning.
    """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Strip leading/trailing whitespace from all string fields
        for field in adapter.field_names():
            value = adapter.get(field)
            if isinstance(value, str):
                adapter[field] = value.strip()

        # Log a warning if a restaurant item is missing its name or link
        if isinstance(item, RestaurantItem):
            if not adapter.get("name") or not adapter.get("link"):
                spider.logger.warning(
                    f"RestaurantItem missing name or link: {dict(adapter)}"
                )

        # Log a warning if a review item has no text
        if isinstance(item, ReviewItem):
            if not adapter.get("review_text"):
                spider.logger.debug(
                    f"ReviewItem has no review_text for restaurant: "
                    f"{adapter.get('restaurant_name')}"
                )

        return item
