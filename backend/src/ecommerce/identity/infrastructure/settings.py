from pydantic import SecretStr
from pydantic_settings import BaseSettings

DEFAULT_SEED_NAME = "Administrator"


class IdentitySettings(BaseSettings):
    session_cookie_secure: bool = False
    admin_seed_email: str | None = None
    admin_seed_password: SecretStr | None = None
    admin_seed_name: str = DEFAULT_SEED_NAME
