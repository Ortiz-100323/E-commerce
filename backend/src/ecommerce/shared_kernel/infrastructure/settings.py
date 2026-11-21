from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ecommerce:ecommerce@localhost:5433/ecommerce"
    log_level: str = "INFO"
