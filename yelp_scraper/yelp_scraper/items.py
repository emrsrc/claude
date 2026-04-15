import scrapy


class RestaurantItem(scrapy.Item):
    """One row per restaurant, collected from the search listing pages."""
    name = scrapy.Field()
    rating = scrapy.Field()
    review_count = scrapy.Field()
    link = scrapy.Field()
    location = scrapy.Field()
    categories = scrapy.Field()
    page_number = scrapy.Field()


class ReviewItem(scrapy.Item):
    """One row per review, collected from each restaurant's detail page."""
    restaurant_name = scrapy.Field()
    restaurant_rating = scrapy.Field()
    restaurant_review_count = scrapy.Field()
    restaurant_link = scrapy.Field()
    restaurant_location = scrapy.Field()
    restaurant_categories = scrapy.Field()
    reviewer_name = scrapy.Field()
    reviewer_rating = scrapy.Field()
    review_text = scrapy.Field()
