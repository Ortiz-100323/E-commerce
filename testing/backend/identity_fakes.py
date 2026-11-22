from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from ecommerce.identity.domain.account import Account, AccountId, EmailAddress
from ecommerce.identity.domain.errors import EmailAlreadyRegistered
from ecommerce.identity.domain.session import Session, token_hash
from ecommerce.shared_kernel.application.audit import AuditEntry
from ecommerce.shared_kernel.domain.principal import Role

SEEDED_AT = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)

ANTONIO_ID = AccountId(UUID("00000000-0000-4000-8000-00000000a001"))
MARIA_ID = AccountId(UUID("00000000-0000-4000-8000-00000000a002"))
BEA_ID = AccountId(UUID("00000000-0000-4000-8000-00000000b001"))

ANTONIO_TOKEN = "antonio-test-session-token-0001"
MARIA_TOKEN = "maria-test-session-token-0000002"
BEA_TOKEN = "bea-buyer-test-session-token-003"

TEST_PASSWORD = "correct horse battery"


class FakeHasher:
    prefix = "fake$v2$"

    def hash(self, password: str) -> str:
        return f"{self.prefix}{password[::-1]}"

    def verify(self, password: str, stored: str) -> bool:
        return stored.startswith("fake$") and stored.split("$", 2)[2] == password[::-1]

    def needs_rehash(self, stored: str) -> bool:
        return not stored.startswith(self.prefix)

    @property
    def dummy_hash(self) -> str:
        return f"{self.prefix}no-account"


class CountingTokens:
    def __init__(self) -> None:
        self.issued = 0

    def new_token(self) -> str:
        self.issued += 1
        return f"token-{self.issued:04d}-" + "x" * 24


def seeded_accounts(password_hash: str) -> list[Account]:
    return [
        Account.create(
            account_id=account_id,
            name=name,
            email=email,
            role=role,
            password_hash=password_hash,
            at=SEEDED_AT,
        )
        for account_id, name, email, role in (
            (ANTONIO_ID, "Antonio", "antonio@example.com", Role.ADMIN),
            (MARIA_ID, "Maria", "maria@example.com", Role.ADMIN),
            (BEA_ID, "Bea", "bea@example.com", Role.BUYER),
        )
    ]


def seeded_sessions(at: datetime) -> list[Session]:
    return [
        Session.start(
            session_id=account_id, account_id=account_id, token_hash=token_hash(token), at=at
        )
        for account_id, token in (
            (ANTONIO_ID, ANTONIO_TOKEN),
            (MARIA_ID, MARIA_TOKEN),
            (BEA_ID, BEA_TOKEN),
        )
    ]


class InMemoryIdentityState:
    def __init__(self) -> None:
        self.accounts: dict[UUID, Account] = {}
        self.sessions: dict[UUID, Session] = {}
        self.audit: list[AuditEntry] = []
        self.commits = 0

    def __call__(self) -> "InMemoryIdentityWork":
        return InMemoryIdentityWork(self)

    def seed(self, hasher: FakeHasher, *, sessions_at: datetime) -> Self:
        for account in seeded_accounts(hasher.hash(TEST_PASSWORD)):
            self.accounts[account.id] = account
        for session in seeded_sessions(sessions_at):
            self.sessions[session.session_id] = session
        return self

    def account_by_email(self, email: str) -> Account | None:
        return next(
            (item for item in self.accounts.values() if item.email.value == email.lower()), None
        )

    def events(self, event: str) -> list[AuditEntry]:
        return [entry for entry in self.audit if entry.event == event]


class InMemoryAccounts:
    def __init__(self, state: InMemoryIdentityState) -> None:
        self._state = state

    async def add(self, account: Account) -> None:
        if self._state.account_by_email(account.email.value) is not None:
            raise EmailAlreadyRegistered()
        self._state.accounts[account.id] = account

    async def by_id(self, account_id: UUID) -> Account | None:
        return self._state.accounts.get(account_id)

    async def by_email(self, email: EmailAddress) -> Account | None:
        return self._state.account_by_email(email.value)

    async def admins(self) -> Sequence[Account]:
        admins = [item for item in self._state.accounts.values() if item.role is Role.ADMIN]
        return sorted(admins, key=lambda item: item.email.value)

    async def any_admin(self) -> bool:
        return any(item.role is Role.ADMIN for item in self._state.accounts.values())

    async def replace_password_hash(self, account_id: UUID, password_hash: str) -> None:
        account = self._state.accounts[account_id]
        self._state.accounts[account_id] = replace(account, password_hash=password_hash)


class InMemorySessions:
    def __init__(self, state: InMemoryIdentityState) -> None:
        self._state = state

    async def add(self, session: Session) -> None:
        self._state.sessions[session.session_id] = session

    async def by_token_hash(self, token_hash: str) -> Session | None:
        return next(
            (item for item in self._state.sessions.values() if item.token_hash == token_hash), None
        )

    async def touch(self, session_id: UUID, at: datetime) -> None:
        self._state.sessions[session_id] = self._state.sessions[session_id].touched(at)

    async def remove(self, session_id: UUID) -> None:
        self._state.sessions.pop(session_id, None)


class InMemoryLogins:
    def __init__(self, state: InMemoryIdentityState) -> None:
        self._state = state

    async def failures_since_last_success(self, login_key: str, since: datetime) -> list[datetime]:
        failures: list[datetime] = []
        for entry in self._state.audit:
            if entry.entity != "login" or entry.entity_id != login_key:
                continue
            if entry.event == "session.logged_in":
                failures = []
            elif entry.event == "session.login_failed" and entry.occurred_at >= since:
                failures.append(entry.occurred_at)
        return failures


class InMemoryIdentityWork:
    def __init__(self, state: InMemoryIdentityState) -> None:
        self._state = state
        self._snapshot: tuple[dict[UUID, Account], dict[UUID, Session]] | None = None
        self._pending: list[AuditEntry] = []

    @property
    def accounts(self) -> InMemoryAccounts:
        return InMemoryAccounts(self._state)

    @property
    def sessions(self) -> InMemorySessions:
        return InMemorySessions(self._state)

    @property
    def logins(self) -> InMemoryLogins:
        return InMemoryLogins(self._state)

    async def lock(self, key: str) -> None:
        return None

    def record(self, entry: AuditEntry) -> None:
        self._pending.append(entry)

    async def __aenter__(self) -> Self:
        self._snapshot = (dict(self._state.accounts), dict(self._state.sessions))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.rollback()

    async def commit(self) -> None:
        self._state.audit.extend(self._pending)
        self._pending = []
        self._snapshot = (dict(self._state.accounts), dict(self._state.sessions))
        self._state.commits += 1

    async def rollback(self) -> None:
        if self._snapshot is not None:
            self._state.accounts, self._state.sessions = (
                dict(self._snapshot[0]),
                dict(self._snapshot[1]),
            )
        self._pending = []
