class WeatherDomainError(Exception):
    pass


class InvalidCity(WeatherDomainError):
    pass
