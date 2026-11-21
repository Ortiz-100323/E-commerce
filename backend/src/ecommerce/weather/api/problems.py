from collections.abc import Mapping

from ecommerce.shared_kernel.api.problem_details import UPSTREAM_UNAVAILABLE, ProblemMapping
from ecommerce.weather.application.errors import WeatherUnavailable

WEATHER_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    WeatherUnavailable: ProblemMapping(UPSTREAM_UNAVAILABLE),
}
