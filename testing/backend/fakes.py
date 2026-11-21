from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.product import Product, ProductId
from ecommerce.catalog.domain.value_objects import Sku
from ecommerce.main import Dependencies
from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.weather.domain.city import City
from ecommerce.weather.domain.weather_search import CurrentWeather, Location, WeatherSearch

LISBON = Location(name="Lisbon", country="Portugal", latitude=38.71667, longitude=-9.13333)
SUNNY = CurrentWeather(temperature_c=21.4, wind_speed_kmh=12.6, weather_code=0)
FIXED_NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class FakeWeatherProvider:
    def __init__(
        self,
        location: Location = LISBON,
        weather: CurrentWeather = SUNNY,
        error: Exception | None = None,
    ) -> None:
        self.location = location
        self.weather = weather
        self.error = error
        self.calls: list[str] = []

    async def current_weather_for(self, city: City) -> tuple[Location, CurrentWeather]:
        self.calls.append(city.value)
        if self.error is not None:
            raise self.error
        return self.location, self.weather


class InMemoryWeatherSearchRepository:
    def __init__(self) -> None:
        self.items: list[WeatherSearch] = []

    async def add(self, search: WeatherSearch) -> None:
        self.items.append(search)

    async def latest(self, limit: int) -> list[WeatherSearch]:
        ordered = sorted(self.items, key=lambda search: search.searched_at, reverse=True)
        return ordered[:limit]


class FakeDatabaseProbe:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def is_up(self) -> bool:
        return self.up


class SequenceClock:
    def __init__(self, *moments: datetime) -> None:
        self.moments = list(moments) or [FIXED_NOW]
        self.index = 0

    def now(self) -> datetime:
        moment = self.moments[min(self.index, len(self.moments) - 1)]
        self.index += 1
        return moment


class InMemoryProductRepository:
    def __init__(self) -> None:
        self.items: dict[ProductId, Product] = {}

    async def add(self, product: Product) -> None:
        self.items[product.id] = product

    async def get(self, product_id: ProductId) -> Product | None:
        return self.items.get(product_id)

    async def get_by_sku(self, sku: Sku) -> Product | None:
        return next((item for item in self.items.values() if item.sku == sku), None)

    async def save(self, product: Product) -> None:
        self.items[product.id] = product


class InMemoryAuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def entries_for(self, entity: str, entity_id: str) -> list[AuditEntry]:
        return [
            entry
            for entry in self.entries
            if (entry.entity, entry.entity_id) == (entity, entity_id)
        ]


class InMemoryCatalogUnitOfWork:
    def __init__(self, catalog: "InMemoryCatalog", actor: Actor | None) -> None:
        self.products = catalog.products
        self.audit_log = catalog.audit_log
        self.actor = actor
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


class InMemoryCatalog:
    def __init__(self) -> None:
        self.products = InMemoryProductRepository()
        self.audit_log = InMemoryAuditLog()
        self.opened: list[InMemoryCatalogUnitOfWork] = []

    def __call__(self, actor: Actor | None = None) -> InMemoryCatalogUnitOfWork:
        work = InMemoryCatalogUnitOfWork(self, actor)
        self.opened.append(work)
        return work


def dependencies_factory(
    *,
    provider: FakeWeatherProvider | None = None,
    repository: InMemoryWeatherSearchRepository | None = None,
    database_up: bool = True,
    clock: SequenceClock | None = None,
    catalog: CatalogUnitOfWorkFactory | None = None,
) -> Callable[[], AbstractAsyncContextManager[Dependencies]]:
    dependencies = Dependencies(
        weather_provider=provider or FakeWeatherProvider(),
        weather_repository=repository or InMemoryWeatherSearchRepository(),
        database_probe=FakeDatabaseProbe(database_up),
        catalog_unit_of_work=catalog or InMemoryCatalog(),
        clock=clock or SequenceClock(),
    )

    @asynccontextmanager
    async def factory() -> AsyncIterator[Dependencies]:
        yield dependencies

    return factory
