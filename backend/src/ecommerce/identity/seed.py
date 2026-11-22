import asyncio
import logging

from ecommerce.identity.application.accounts import NewAccount, SeedFirstAdmin
from ecommerce.identity.application.ports import IdentityUnitOfWorkFactory, PasswordHasher
from ecommerce.identity.domain.errors import EmailAlreadyRegistered
from ecommerce.identity.infrastructure.security import ScryptPasswordHasher
from ecommerce.identity.infrastructure.settings import IdentitySettings
from ecommerce.identity.infrastructure.unit_of_work import SqlAlchemyIdentityUnitOfWorkFactory
from ecommerce.shared_kernel.application.ports import Clock, SystemClock
from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.infrastructure.database import create_engine, create_session_factory
from ecommerce.shared_kernel.infrastructure.logging import configure_logging
from ecommerce.shared_kernel.infrastructure.settings import Settings

logger = logging.getLogger("ecommerce.identity.seed")


async def seed_first_admin(
    identity: IdentityUnitOfWorkFactory,
    hasher: PasswordHasher,
    clock: Clock,
    settings: IdentitySettings,
) -> int:
    email = (settings.admin_seed_email or "").strip()
    password = settings.admin_seed_password
    if not email or password is None:
        async with identity() as work:
            has_admin = await work.accounts.any_admin()
        if not has_admin:
            logger.warning(
                "no administrator exists and ADMIN_SEED_EMAIL or ADMIN_SEED_PASSWORD is not set"
            )
        return 0
    new = NewAccount(
        name=settings.admin_seed_name, email=email, password=password.get_secret_value()
    )
    try:
        created = await SeedFirstAdmin(identity, hasher, clock).execute(new)
    except EmailAlreadyRegistered:
        logger.warning("the seed email already belongs to a customer account; no admin created")
        return 0
    except DomainValidationError as error:
        fields = ", ".join(sorted({issue.field for issue in error.issues}))
        logger.error("the seed administrator is not valid: %s", fields)
        return 1
    if created is None:
        logger.info("an administrator already exists; the seed changed nothing")
    else:
        logger.info("created the first administrator")
    return 0


async def run() -> int:
    settings = Settings()
    engine = create_engine(settings.database_url)
    try:
        return await seed_first_admin(
            SqlAlchemyIdentityUnitOfWorkFactory(create_session_factory(engine)),
            ScryptPasswordHasher(),
            SystemClock(),
            IdentitySettings(),
        )
    finally:
        await engine.dispose()


def main() -> int:
    configure_logging(Settings().log_level)
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
