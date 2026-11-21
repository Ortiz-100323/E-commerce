from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.weather.api.schemas import (
    ErrorResponse,
    WeatherSearchRequest,
    WeatherSearchResponse,
)
from ecommerce.weather.application.errors import CityNotFound, WeatherUnavailable
from ecommerce.weather.application.list_weather_searches import ListWeatherSearches
from ecommerce.weather.application.ports import WeatherProvider
from ecommerce.weather.application.search_weather import SearchWeather
from ecommerce.weather.domain.errors import InvalidCity
from ecommerce.weather.domain.repository import WeatherSearchRepository

router = APIRouter(prefix="/weather", tags=["weather (temporary)"])


def get_search_weather(request: Request) -> SearchWeather:
    state = request.app.state
    provider: WeatherProvider = state.weather_provider
    repository: WeatherSearchRepository = state.weather_repository
    clock: Clock = state.clock
    return SearchWeather(provider, repository, clock)


def get_list_weather_searches(request: Request) -> ListWeatherSearches:
    repository: WeatherSearchRepository = request.app.state.weather_repository
    return ListWeatherSearches(repository)


@router.post(
    "/searches",
    status_code=status.HTTP_201_CREATED,
    summary="Look up the current weather for a city and save the search",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
    },
)
async def search_weather(
    body: WeatherSearchRequest,
    use_case: Annotated[SearchWeather, Depends(get_search_weather)],
) -> WeatherSearchResponse:
    try:
        view = await use_case.execute(body.city)
    except InvalidCity as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    except CityNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "City not found.") from error
    except WeatherUnavailable as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The weather service is unavailable. Try again later."
        ) from error
    return WeatherSearchResponse.model_validate(view)


@router.get("/searches", summary="List the latest searches, newest first")
async def list_weather_searches(
    use_case: Annotated[ListWeatherSearches, Depends(get_list_weather_searches)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[WeatherSearchResponse]:
    views = await use_case.execute(limit)
    return [WeatherSearchResponse.model_validate(view) for view in views]
