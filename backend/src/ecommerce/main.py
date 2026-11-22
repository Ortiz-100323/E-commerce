from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from ecommerce.catalog.api.imports_router import handle_import_file_rejected
from ecommerce.catalog.api.imports_router import router as imports_router
from ecommerce.catalog.api.problems import CATALOG_PROBLEMS, IMPORT_PROBLEMS
from ecommerce.catalog.api.router import categories_router
from ecommerce.catalog.api.router import router as catalog_router
from ecommerce.catalog.application.importing import (
    ExistingProducts,
    ImportFileReader,
    ImportFileRejected,
)
from ecommerce.catalog.application.products import ProductQueries
from ecommerce.catalog.application.unit_of_work import CatalogUnitOfWorkFactory
from ecommerce.catalog.domain.importing.policies import ImportPolicies
from ecommerce.catalog.infrastructure.csv_reader import CsvImportReader
from ecommerce.catalog.infrastructure.import_settings import ImportSettings
from ecommerce.catalog.infrastructure.product_queries import SqlAlchemyProductQueries
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

API_PREFIX = "/api/v1"

INFRASTRUCTURE_PROBLEMS: Mapping[type[Exception], ProblemMapping] = {
    OperationalError: ProblemMapping(SERVICE_UNAVAILABLE, headers={"Retry-After": "1"}),
}


@dataclass(frozen=True)
class Dependencies:
    database_probe: DatabaseProbe
    catalog_unit_of_work: CatalogUnitOfWorkFactory
    catalog_queries: ProductQueries
    existing_products: ExistingProducts
    import_reader: ImportFileReader
    import_policies: ImportPolicies
    clock: Clock


DependenciesFactory = Callable[[], AbstractAsyncContextManager[Dependencies]]


@asynccontextmanager
async def production_dependencies() -> AsyncIterator[Dependencies]:
    settings = Settings()
    policies = ImportSettings().policies()
    engine = create_engine(settings.database_url)
    queries = SqlAlchemyProductQueries(engine)
    try:
        yield Dependencies(
            database_probe=SqlAlchemyDatabaseProbe(engine),
            catalog_unit_of_work=SqlAlchemyCatalogUnitOfWorkFactory(create_session_factory(engine)),
            catalog_queries=queries,
            existing_products=queries,
            import_reader=CsvImportReader(),
            import_policies=policies,
            clock=SystemClock(),
        )
    finally:
        await engine.dispose()


def create_app(dependencies_factory: DependenciesFactory = production_dependencies) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with dependencies_factory() as dependencies:
            app.state.database_probe = dependencies.database_probe
            app.state.catalog_unit_of_work = dependencies.catalog_unit_of_work
            app.state.catalog_queries = dependencies.catalog_queries
            app.state.existing_products = dependencies.existing_products
            app.state.import_reader = dependencies.import_reader
            app.state.import_policies = dependencies.import_policies
            app.state.clock = dependencies.clock
            yield

    app = FastAPI(title="E-commerce API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    install_problem_handlers(
        app, {**INFRASTRUCTURE_PROBLEMS, **CATALOG_PROBLEMS, **IMPORT_PROBLEMS}
    )
    app.add_exception_handler(ImportFileRejected, handle_import_file_rejected)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(catalog_router, prefix=API_PREFIX)
    app.include_router(categories_router, prefix=API_PREFIX)
    app.include_router(imports_router, prefix=API_PREFIX)
    return app


def create_production_app() -> FastAPI:
    configure_logging(Settings().log_level)
    return create_app()
