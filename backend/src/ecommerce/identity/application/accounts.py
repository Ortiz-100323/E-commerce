import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from ecommerce.identity.application.ports import (
    IdentityUnitOfWork,
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    TokenSource,
)
from ecommerce.identity.domain.account import (
    Account,
    AccountName,
    EmailAddress,
    new_account_id,
)
from ecommerce.identity.domain.errors import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    TooManyLoginAttempts,
)
from ecommerce.identity.domain.password import MAX_PASSWORD_LENGTH, Password
from ecommerce.identity.domain.session import MAX_TOKEN_LENGTH, Session, token_hash
from ecommerce.identity.domain.throttle import WINDOW, login_key, retry_after
from ecommerce.shared_kernel.application.audit import AuditEntry, JsonObject
from ecommerce.shared_kernel.application.ports import Clock
from ecommerce.shared_kernel.domain.errors import DomainValidationError, IssueCollector
from ecommerce.shared_kernel.domain.principal import AdminRequired, Principal, Role

ACCOUNT_ENTITY = "account"
LOGIN_ENTITY = "login"
ACCOUNT_CREATED = "account.created"
LOGGED_IN = "session.logged_in"
LOGGED_OUT = "session.logged_out"
LOGIN_FAILED = "session.login_failed"
ANONYMOUS = "Anonymous"
SEED_ACTOR = "Seed"


@dataclass(frozen=True, kw_only=True)
class NewAccount:
    name: str
    email: str
    password: str


@dataclass(frozen=True, kw_only=True)
class LoggedIn:
    token: str
    principal: Principal


def account_entry(account: Account, *, actor: str, source: str, at: datetime) -> AuditEntry:
    return AuditEntry(
        occurred_at=at,
        actor=actor,
        event=ACCOUNT_CREATED,
        entity=ACCOUNT_ENTITY,
        entity_id=str(account.id),
        sku=None,
        before=None,
        after={"name": account.name.value, "email": account.email.value, "role": account.role},
        context={"source": source},
    )


def login_entry(
    event: str, key: str, *, actor: str, at: datetime, context: JsonObject
) -> AuditEntry:
    return AuditEntry(
        occurred_at=at,
        actor=actor,
        event=event,
        entity=LOGIN_ENTITY,
        entity_id=key,
        sku=None,
        before=None,
        after=None,
        context=context,
    )


def checked_new_account(new: NewAccount) -> tuple[AccountName, EmailAddress, Password]:
    collector = IssueCollector()
    name = collector.attempt(AccountName, new.name)
    email = collector.attempt(EmailAddress, new.email)
    password = collector.attempt(Password, new.password)
    if collector.issues:
        raise DomainValidationError(collector.issues)
    assert name is not None and email is not None and password is not None
    return name, email, password


async def create_account(
    work: IdentityUnitOfWork,
    hasher: PasswordHasher,
    new: NewAccount,
    role: Role,
    at: datetime,
) -> Account:
    name, email, password = checked_new_account(new)
    await work.lock(f"account-email:{email.value}")
    if await work.accounts.by_email(email) is not None:
        raise EmailAlreadyRegistered()
    password_hash = await asyncio.to_thread(hasher.hash, password.value)
    account = Account.create(
        account_id=new_account_id(),
        name=name.value,
        email=email.value,
        role=role,
        password_hash=password_hash,
        at=at,
    )
    await work.accounts.add(account)
    return account


async def start_session(
    work: IdentityUnitOfWork, tokens: TokenSource, account: Account, at: datetime
) -> str:
    token = tokens.new_token()
    await work.sessions.add(
        Session.start(
            session_id=uuid4(), account_id=account.id, token_hash=token_hash(token), at=at
        )
    )
    return token


class LogIn:
    def __init__(
        self,
        identity: IdentityUnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: TokenSource,
        clock: Clock,
    ) -> None:
        self._identity = identity
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock

    async def execute(self, email: str, password: str) -> LoggedIn:
        now = self._clock.now()
        key = login_key(email)
        address = self._address(email)
        async with self._identity() as work:
            await work.lock(f"login:{key}")
            wait = retry_after(
                await work.logins.failures_since_last_success(key, now - WINDOW), now
            )
            if wait is not None:
                raise TooManyLoginAttempts(wait)
            account = None if address is None else await work.accounts.by_email(address)
            stored = self._hasher.dummy_hash if account is None else account.password_hash
            matches = len(password) <= MAX_PASSWORD_LENGTH and await asyncio.to_thread(
                self._hasher.verify, password, stored
            )
            if account is None or not matches or not account.active:
                work.record(
                    login_entry(
                        LOGIN_FAILED, key, actor=ANONYMOUS, at=now, context={"email": email[:254]}
                    )
                )
                await work.commit()
                raise InvalidCredentials()
            if self._hasher.needs_rehash(account.password_hash):
                fresh = await asyncio.to_thread(self._hasher.hash, password)
                await work.accounts.replace_password_hash(account.id, fresh)
            token = await start_session(work, self._tokens, account, now)
            work.record(
                login_entry(
                    LOGGED_IN,
                    key,
                    actor=account.name.value,
                    at=now,
                    context={"account_id": str(account.id), "role": account.role},
                )
            )
            await work.commit()
        return LoggedIn(token=token, principal=account.principal())

    @staticmethod
    def _address(email: str) -> EmailAddress | None:
        try:
            return EmailAddress(email)
        except DomainValidationError:
            return None


class Authenticate:
    def __init__(self, identity: IdentityUnitOfWorkFactory, clock: Clock) -> None:
        self._identity = identity
        self._clock = clock

    async def execute(self, token: str) -> Principal | None:
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return None
        now = self._clock.now()
        async with self._identity() as work:
            session = await work.sessions.by_token_hash(token_hash(token))
            if session is None or not session.is_active(now):
                return None
            account = await work.accounts.by_id(session.account_id)
            if account is None or not account.active:
                return None
            if session.needs_touch(now):
                await work.sessions.touch(session.session_id, now)
                await work.commit()
        return account.principal()


class LogOut:
    def __init__(self, identity: IdentityUnitOfWorkFactory, clock: Clock) -> None:
        self._identity = identity
        self._clock = clock

    async def execute(self, token: str) -> None:
        if not token or len(token) > MAX_TOKEN_LENGTH:
            return
        now = self._clock.now()
        async with self._identity() as work:
            session = await work.sessions.by_token_hash(token_hash(token))
            if session is None:
                return
            account = await work.accounts.by_id(session.account_id)
            await work.sessions.remove(session.session_id)
            if account is not None:
                work.record(
                    login_entry(
                        LOGGED_OUT,
                        login_key(account.email.value),
                        actor=account.name.value,
                        at=now,
                        context={"account_id": str(account.id)},
                    )
                )
            await work.commit()


class CreateAdmin:
    def __init__(
        self, identity: IdentityUnitOfWorkFactory, hasher: PasswordHasher, clock: Clock
    ) -> None:
        self._identity = identity
        self._hasher = hasher
        self._clock = clock

    async def execute(self, new: NewAccount, creator: Principal) -> Account:
        if not creator.is_admin:
            raise AdminRequired()
        now = self._clock.now()
        async with self._identity() as work:
            account = await create_account(work, self._hasher, new, Role.ADMIN, now)
            work.record(account_entry(account, actor=creator.name, source="admin", at=now))
            await work.commit()
        return account


class ListAdmins:
    def __init__(self, identity: IdentityUnitOfWorkFactory) -> None:
        self._identity = identity

    async def execute(self) -> list[Account]:
        async with self._identity() as work:
            return list(await work.accounts.admins())


class SignUp:
    def __init__(
        self,
        identity: IdentityUnitOfWorkFactory,
        hasher: PasswordHasher,
        tokens: TokenSource,
        clock: Clock,
    ) -> None:
        self._identity = identity
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock

    async def execute(self, new: NewAccount) -> LoggedIn:
        now = self._clock.now()
        async with self._identity() as work:
            account = await create_account(work, self._hasher, new, Role.BUYER, now)
            token = await start_session(work, self._tokens, account, now)
            work.record(account_entry(account, actor=account.name.value, source="sign-up", at=now))
            await work.commit()
        return LoggedIn(token=token, principal=account.principal())


class SeedFirstAdmin:
    def __init__(
        self, identity: IdentityUnitOfWorkFactory, hasher: PasswordHasher, clock: Clock
    ) -> None:
        self._identity = identity
        self._hasher = hasher
        self._clock = clock

    async def execute(self, new: NewAccount) -> Account | None:
        now = self._clock.now()
        async with self._identity() as work:
            await work.lock("seed-first-admin")
            if await work.accounts.any_admin():
                return None
            account = await create_account(work, self._hasher, new, Role.ADMIN, now)
            work.record(account_entry(account, actor=SEED_ACTOR, source="seed", at=now))
            await work.commit()
        return account
