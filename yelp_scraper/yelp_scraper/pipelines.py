from itemadapter import ItemAdapter
from yelp_scraper.items import ReviewItem


class CsvExportPipeline:
    """
    Pass-through pipeline.  Actual CSV writing is handled by Scrapy's
    built-in FEEDS setting (see settings.py).  RestaurantItem has been
    removed; ReviewItem is the sole output type.  Restaurants with no
    scraped reviews appear as sentinel rows with blank review fields.
    """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Strip leading/trailing whitespace from all string fields
        for field in adapter.field_names():
            value = adapter.get(field)
            if isinstance(value, str):
                adapter[field] = value.strip()

        if isinstance(item, ReviewItem):
            if not adapter.get("restaurant_name") or not adapter.get("restaurant_link"):
                spider.logger.warning(
                    f"ReviewItem missing restaurant_name or restaurant_link: {dict(adapter)}"
                )

        return item
