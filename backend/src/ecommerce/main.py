from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from ecommerce.catalog.api.router import router as catalog_router
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.infrastructure.unit_of_work import SqlAlchemyCatalogUnitOfWorkFactory
from ecommerce.shared_kernel.api.exception_handlers import install_problem_handlers
from ecommerce.shared_kernel.api.health_router import router as health_router
from ecommerce.shared_kernel.api.problem_details import SERVICE_UNAVAILABLE, ProblemMapping
from ecommerce.shared_kernel.application.ports import Clock, DatabaseProbe, SystemClock
from ecommerce.shared_kernel.infrastructure.database import (
    SqlAlchemyDatabaseProbe,
    create_engine,
    create_session_factory,
)
from ecommerce.shared_kernel.infrastructure.logging import configure_logging
from ecommerce.shared_kernel.infrastructure.request_id_middleware import RequestIdMiddleware
from ecommerce.shared_kernel.infrastructure.settings import Settings
from ecommerce.weather.api.problems import WEATHER_PROBLEMS
from ecommerce.weather.api.router import router as weather_router
from ecommerce.weather.application.ports import WeatherProvider
from ecommerce.weather.domain.repository import WeatherSearchRepository
from ecommerce.weather.infrastructure.open_meteo import OpenMeteoWeatherProvider
from ecommerce.weather.infrastructure.repository import SqlAlchemyWeatherSearchRepository

API_PREFIX = "/api/v1"

INFRASTRUCTURE_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    OperationalError: ProblemMapping(SERVICE_UNAVAILABLE, headers={"Retry-After": "1"}),
}


@dataclass(frozen=True)
class Dependencies:
    weather_provider: WeatherProvider
    weather_repository: WeatherSearchRepository
    database_probe: DatabaseProbe
    catalog_unit_of_work: CatalogUnitOfWorkFactory
    clock: Clock


DependenciesFactory = Callable[[], AbstractAsyncContextManager[Dependencies]]


@asynccontextmanager
async def production_dependencies() -> AsyncIterator[Dependencies]:
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            yield Dependencies(
                weather_provider=OpenMeteoWeatherProvider(
                    client, settings.open_meteo_geocoding_url, settings.open_meteo_forecast_url
                ),
                weather_repository=SqlAlchemyWeatherSearchRepository(engine),
                database_probe=SqlAlchemyDatabaseProbe(engine),
                catalog_unit_of_work=SqlAlchemyCatalogUnitOfWorkFactory(
                    create_session_factory(engine)
                ),
                clock=SystemClock(),
            )
    finally:
        await engine.dispose()


def create_app(dependencies_factory: DependenciesFactory = production_dependencies) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with dependencies_factory() as dependencies:
            app.state.weather_provider = dependencies.weather_provider
            app.state.weather_repository = dependencies.weather_repository
            app.state.database_probe = dependencies.database_probe
            app.state.catalog_unit_of_work = dependencies.catalog_unit_of_work
            app.state.clock = dependencies.clock
            yield

    app = FastAPI(title="E-commerce API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    install_problem_handlers(app, {**INFRASTRUCTURE_PROBLEMS, **WEATHER_PROBLEMS})
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(catalog_router, prefix=API_PREFIX)
    app.include_router(weather_router, prefix=API_PREFIX)
    return app


def create_production_app() -> FastAPI:
    configure_logging(Settings().log_level)
    return create_app()
