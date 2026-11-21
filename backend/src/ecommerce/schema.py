from ecommerce.catalog.infrastructure.orm import products
from ecommerce.shared_kernel.infrastructure.audit import audit_log
from ecommerce.shared_kernel.infrastructure.database import metadata
from ecommerce.weather.infrastructure.orm import weather_searches

TABLES = (audit_log, products, weather_searches)

__all__ = ["TABLES", "metadata"]
