from ecommerce.shared_kernel.domain.errors import NotFoundError


class CityNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__("City not found.")


class WeatherUnavailable(Exception):
    pass
