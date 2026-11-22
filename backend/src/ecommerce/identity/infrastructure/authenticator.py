from ecommerce.identity.application.accounts import Authenticate
from ecommerce.identity.application.ports import IdentityUnitOfWorkFactory
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.principal import Principal


class SessionAuthenticator:
    def __init__(self, identity: IdentityUnitOfWorkFactory, clock: Clock) -> None:
        self._authenticate = Authenticate(identity, clock)

    async def authenticate(self, token: str) -> Principal | None:
        return await self._authenticate.execute(token)
