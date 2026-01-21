"""Product-based strategy configuration"""

def get_product_config(product_key):
    """Get configuration for product type"""
    return PRODUCT_CONFIGS.get(product_key, PRODUCT_CONFIGS["general"])


PRODUCT_CONFIGS = {
    "luxury_cars": {
        "strategy": "consultative",
        "context": "luxury vehicles"
    },
    "enterprise_software": {
        "strategy": "consultative",
        "context": "enterprise software solutions"
    },
    "coaching": {
        "strategy": "consultative",
        "context": "high-ticket coaching programs"
    },
    "budget_fragrances": {
        "strategy": "transactional",
        "context": "$30 fragrances"
    },
    "retail_clothing": {
        "strategy": "transactional",
        "context": "retail clothing"
    },
    "general": {
        "strategy": "consultative",
        "context": "general products/services"
    }
}

