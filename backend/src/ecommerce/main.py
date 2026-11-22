from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta

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
from ecommerce.identity.api.problems import IDENTITY_PROBLEMS, handle_too_many_login_attempts
from ecommerce.identity.api.router import router as identity_router
from ecommerce.identity.application.ports import (
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    TokenSource,
)
from ecommerce.identity.domain.errors import TooManyLoginAttempts
from ecommerce.identity.infrastructure.authenticator import SessionAuthenticator
from ecommerce.identity.infrastructure.security import ScryptPasswordHasher, SecretTokenSource
from ecommerce.identity.infrastructure.settings import IdentitySettings
from ecommerce.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWorkFactory
from ecommerce.integration.catalog_sales import CatalogSales
from ecommerce.ordering.api.problems import ORDERING_PROBLEMS
from ecommerce.ordering.api.router import admin_orders_router, me_router
from ecommerce.ordering.api.router import router as orders_router
from ecommerce.ordering.application.ports import PaymentGateway, TransientErrors
from ecommerce.ordering.application.unit_of_work import OrderingUnitOfWorkFactory
from ecommerce.ordering.infrastructure.payment_gateway import FakePaymentGateway
from ecommerce.ordering.infrastructure.settings import CheckoutSettings
from ecommerce.ordering.infrastructure.transient import DatabaseTransientErrors
from ecommerce.ordering.infrastructure.unit_of_work import SqlAlchemyOrderingUnitOfWorkFactory
from ecommerce.shared_kernel.api.access import ACCESS_PROBLEMS
from ecommerce.shared_kernel.api.exception_handlers import install_problem_handlers
from ecommerce.shared_kernel.api.health_router import router as health_router
from ecommerce.shared_kernel.api.problem_details import SERVICE_UNAVAILABLE, ProblemMapping
from ecommerce.shared_kernel.api.same_site import SameSiteMiddleware
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
    ordering_unit_of_work: OrderingUnitOfWorkFactory
    payment_gateway: PaymentGateway
    transient_errors: TransientErrors
    idempotency_key_lifetime: timedelta
    checkout_fingerprint_secret: bytes
    identity_unit_of_work: IdentityUnitOfWorkFactory
    password_hasher: PasswordHasher
    session_clock: Clock
    session_cookie_secure: bool = False
    token_source: TokenSource = field(default_factory=SecretTokenSource)


DependenciesFactory = Callable[[], AbstractAsyncContextManager[Dependencies]]


@asynccontextmanager
async def production_dependencies() -> AsyncIterator[Dependencies]:
    settings = Settings()
    policies = ImportSettings().policies()
    checkout = CheckoutSettings()
    identity = IdentitySettings()
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    queries = SqlAlchemyProductQueries(engine)
    try:
        yield Dependencies(
            database_probe=SqlAlchemyDatabaseProbe(engine),
            catalog_unit_of_work=SqlAlchemyCatalogUnitOfWorkFactory(sessions),
            catalog_queries=queries,
            existing_products=queries,
            import_reader=CsvImportReader(),
            import_policies=policies,
            clock=SystemClock(),
            ordering_unit_of_work=SqlAlchemyOrderingUnitOfWorkFactory(
                sessions, CatalogSales, lock_timeout_ms=checkout.lock_timeout_ms
            ),
            payment_gateway=FakePaymentGateway(),
            transient_errors=DatabaseTransientErrors(),
            idempotency_key_lifetime=checkout.idempotency_key_lifetime,
            checkout_fingerprint_secret=checkout.fingerprint_key,
            identity_unit_of_work=SqlAlchemyIdentityUnitOfWorkFactory(sessions),
            password_hasher=ScryptPasswordHasher(),
            session_clock=SystemClock(),
            session_cookie_secure=identity.session_cookie_secure,
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
            app.state.ordering_unit_of_work = dependencies.ordering_unit_of_work
            app.state.payment_gateway = dependencies.payment_gateway
            app.state.transient_errors = dependencies.transient_errors
            app.state.idempotency_key_lifetime = dependencies.idempotency_key_lifetime
            app.state.checkout_fingerprint_secret = dependencies.checkout_fingerprint_secret
            app.state.identity_unit_of_work = dependencies.identity_unit_of_work
            app.state.password_hasher = dependencies.password_hasher
            app.state.token_source = dependencies.token_source
            app.state.session_clock = dependencies.session_clock
            app.state.session_cookie_secure = dependencies.session_cookie_secure
            app.state.authenticator = SessionAuthenticator(
                dependencies.identity_unit_of_work, dependencies.session_clock
            )
            yield

    app = FastAPI(title="E-commerce API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(SameSiteMiddleware)
    app.add_middleware(RequestIdMiddleware)
    install_problem_handlers(
        app,
        {
            **INFRASTRUCTURE_PROBLEMS,
            **ACCESS_PROBLEMS,
            **IDENTITY_PROBLEMS,
            **CATALOG_PROBLEMS,
            **IMPORT_PROBLEMS,
            **ORDERING_PROBLEMS,
        },
    )
    app.add_exception_handler(ImportFileRejected, handle_import_file_rejected)
    app.add_exception_handler(TooManyLoginAttempts, handle_too_many_login_attempts)
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(identity_router, prefix=API_PREFIX)
    app.include_router(catalog_router, prefix=API_PREFIX)
    app.include_router(categories_router, prefix=API_PREFIX)
    app.include_router(imports_router, prefix=API_PREFIX)
    app.include_router(orders_router, prefix=API_PREFIX)
    app.include_router(me_router, prefix=API_PREFIX)
    app.include_router(admin_orders_router, prefix=API_PREFIX)
    return app


def create_production_app() -> FastAPI:
    configure_logging(Settings().log_level)
    return create_app()
