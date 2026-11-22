from datetime import UTC, datetime, timedelta

import pytest
from identity_fakes import (
    ANTONIO_TOKEN,
    BEA_TOKEN,
    TEST_PASSWORD,
    CountingTokens,
    FakeHasher,
    InMemoryIdentityState,
)

from ecommerce.identity.application.accounts import (
    Authenticate,
    CreateAdmin,
    ListAdmins,
    LogIn,
    LogOut,
    NewAccount,
    SeedFirstAdmin,
    SignUp,
)
from ecommerce.identity.domain.errors import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    TooManyLoginAttempts,
)
from ecommerce.identity.domain.session import ABSOLUTE_LIFETIME, IDLE_TIMEOUT, TOUCH_EVERY
from ecommerce.identity.domain.throttle import MAX_FAILURES, WINDOW
from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.domain.principal import AdminRequired, Principal, Role
from ordering_fakes import MovableClock

START = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)


class World:
    def __init__(self) -> None:
        self.clock = MovableClock(START)
        self.hasher = FakeHasher()
        self.tokens = CountingTokens()
        self.state = InMemoryIdentityState().seed(self.hasher, sessions_at=START)

    def log_in(self) -> LogIn:
        return LogIn(self.state, self.hasher, self.tokens, self.clock)

    def authenticate(self) -> Authenticate:
        return Authenticate(self.state, self.clock)


@pytest.fixture
def world() -> World:
    return World()


async def admin_principal(world: World) -> Principal:
    principal = await world.authenticate().execute(ANTONIO_TOKEN)
    assert principal is not None
    return principal


class TestLogIn:
    async def test_an_admin_logs_in_and_gets_a_session(self, world: World) -> None:
        result = await world.log_in().execute(" Antonio@Example.com ", TEST_PASSWORD)

        assert (result.principal.name, result.principal.role) == ("Antonio", Role.ADMIN)
        assert (await world.authenticate().execute(result.token)) == result.principal
        assert [entry.actor for entry in world.state.events("session.logged_in")] == ["Antonio"]

    async def test_a_buyer_logs_in_as_a_buyer(self, world: World) -> None:
        result = await world.log_in().execute("bea@example.com", TEST_PASSWORD)

        assert result.principal.role is Role.BUYER

    @pytest.mark.parametrize(
        ("email", "password"),
        [
            ("antonio@example.com", "wrong password!"),
            ("nobody@example.com", TEST_PASSWORD),
            ("not an email", TEST_PASSWORD),
            ("antonio@example.com", "x" * 5000),
        ],
    )
    async def test_every_failure_looks_the_same(
        self, world: World, email: str, password: str
    ) -> None:
        with pytest.raises(InvalidCredentials) as raised:
            await world.log_in().execute(email, password)

        assert str(raised.value) == "The email or password is incorrect."
        assert len(world.state.events("session.login_failed")) == 1
        assert world.tokens.issued == 0

    async def test_the_sixth_attempt_is_refused_even_with_the_right_password(
        self, world: World
    ) -> None:
        for _ in range(MAX_FAILURES):
            with pytest.raises(InvalidCredentials):
                await world.log_in().execute("antonio@example.com", "wrong password!")
            world.clock.advance(timedelta(seconds=30))

        with pytest.raises(TooManyLoginAttempts) as raised:
            await world.log_in().execute("antonio@example.com", TEST_PASSWORD)

        expected = WINDOW - timedelta(seconds=30 * MAX_FAILURES)
        assert raised.value.retry_after_seconds == int(expected.total_seconds())
        assert len(world.state.events("session.login_failed")) == MAX_FAILURES

    async def test_the_lock_lifts_after_the_window(self, world: World) -> None:
        for _ in range(MAX_FAILURES):
            with pytest.raises(InvalidCredentials):
                await world.log_in().execute("antonio@example.com", "wrong password!")

        world.clock.advance(WINDOW)

        result = await world.log_in().execute("antonio@example.com", TEST_PASSWORD)
        assert result.principal.name == "Antonio"

    async def test_a_success_clears_earlier_failures(self, world: World) -> None:
        for _ in range(MAX_FAILURES - 1):
            with pytest.raises(InvalidCredentials):
                await world.log_in().execute("antonio@example.com", "wrong password!")
        await world.log_in().execute("antonio@example.com", TEST_PASSWORD)

        for _ in range(MAX_FAILURES - 1):
            with pytest.raises(InvalidCredentials):
                await world.log_in().execute("antonio@example.com", "wrong password!")
        result = await world.log_in().execute("antonio@example.com", TEST_PASSWORD)

        assert result.principal.name == "Antonio"

    async def test_the_lock_is_per_email(self, world: World) -> None:
        for _ in range(MAX_FAILURES):
            with pytest.raises(InvalidCredentials):
                await world.log_in().execute("antonio@example.com", "wrong password!")

        result = await world.log_in().execute("maria@example.com", TEST_PASSWORD)

        assert result.principal.name == "Maria"

    async def test_an_old_hash_is_upgraded_at_log_in(self, world: World) -> None:
        account = world.state.account_by_email("bea@example.com")
        assert account is not None
        world.state.accounts[account.id] = account.__class__(
            **{**account.__dict__, "password_hash": "fake$v1$" + TEST_PASSWORD[::-1]}
        )

        await world.log_in().execute("bea@example.com", TEST_PASSWORD)

        upgraded = world.state.account_by_email("bea@example.com")
        assert upgraded is not None and upgraded.password_hash.startswith(FakeHasher.prefix)

    async def test_logging_in_twice_gives_two_independent_sessions(self, world: World) -> None:
        first = await world.log_in().execute("antonio@example.com", TEST_PASSWORD)
        second = await world.log_in().execute("antonio@example.com", TEST_PASSWORD)

        await LogOut(world.state, world.clock).execute(first.token)

        assert await world.authenticate().execute(first.token) is None
        assert await world.authenticate().execute(second.token) is not None


class TestSessions:
    async def test_ends_after_30_idle_minutes(self, world: World) -> None:
        world.clock.advance(IDLE_TIMEOUT)

        assert await world.authenticate().execute(ANTONIO_TOKEN) is None

    async def test_activity_keeps_it_alive_until_8_hours(self, world: World) -> None:
        while world.clock.now() + timedelta(minutes=25) < START + ABSOLUTE_LIFETIME:
            world.clock.advance(timedelta(minutes=25))
            assert await world.authenticate().execute(ANTONIO_TOKEN) is not None

        world.clock.current = START + ABSOLUTE_LIFETIME
        assert await world.authenticate().execute(ANTONIO_TOKEN) is None

    async def test_writes_activity_at_most_once_a_minute(self, world: World) -> None:
        commits = world.state.commits
        world.clock.advance(TOUCH_EVERY - timedelta(seconds=1))
        await world.authenticate().execute(ANTONIO_TOKEN)
        assert world.state.commits == commits

        world.clock.advance(timedelta(seconds=1))
        await world.authenticate().execute(ANTONIO_TOKEN)
        assert world.state.commits == commits + 1

    @pytest.mark.parametrize("token", ["", "made-up-token", "x" * 500, ANTONIO_TOKEN + "x"])
    async def test_an_unknown_token_is_nobody(self, world: World, token: str) -> None:
        assert await world.authenticate().execute(token) is None

    async def test_logging_out_twice_is_harmless(self, world: World) -> None:
        log_out = LogOut(world.state, world.clock)

        await log_out.execute(ANTONIO_TOKEN)
        await log_out.execute(ANTONIO_TOKEN)

        assert await world.authenticate().execute(ANTONIO_TOKEN) is None
        assert len(world.state.events("session.logged_out")) == 1

    async def test_an_inactive_account_loses_its_sessions(self, world: World) -> None:
        account = world.state.account_by_email("antonio@example.com")
        assert account is not None
        world.state.accounts[account.id] = account.__class__(
            **{**account.__dict__, "active": False}
        )

        assert await world.authenticate().execute(ANTONIO_TOKEN) is None


ANA = NewAccount(name="Ana Souza", email="ana@example.com", password="another long password")


class TestAdmins:
    async def test_an_admin_creates_an_admin_who_can_log_in(self, world: World) -> None:
        creator = await admin_principal(world)

        created = await CreateAdmin(world.state, world.hasher, world.clock).execute(ANA, creator)
        logged_in = await world.log_in().execute("ana@example.com", ANA.password)

        assert created.role is Role.ADMIN
        assert logged_in.principal.role is Role.ADMIN
        entry = world.state.events("account.created")[-1]
        assert (entry.actor, entry.context["source"]) == ("Antonio", "admin")
        assert ANA.password not in repr(world.state.audit)

    async def test_a_buyer_cannot_create_an_admin(self, world: World) -> None:
        buyer = await world.authenticate().execute(BEA_TOKEN)
        assert buyer is not None

        with pytest.raises(AdminRequired):
            await CreateAdmin(world.state, world.hasher, world.clock).execute(ANA, buyer)

        assert world.state.account_by_email("ana@example.com") is None

    async def test_a_buyers_email_cannot_be_turned_into_an_admin(self, world: World) -> None:
        creator = await admin_principal(world)
        taken = NewAccount(name="Bea", email="BEA@example.com", password="another long password")

        with pytest.raises(EmailAlreadyRegistered):
            await CreateAdmin(world.state, world.hasher, world.clock).execute(taken, creator)

        bea = world.state.account_by_email("bea@example.com")
        assert bea is not None and bea.role is Role.BUYER

    async def test_reports_every_invalid_field(self, world: World) -> None:
        creator = await admin_principal(world)

        with pytest.raises(DomainValidationError) as raised:
            await CreateAdmin(world.state, world.hasher, world.clock).execute(
                NewAccount(name="", email="nope", password="short"), creator
            )

        assert [issue.field for issue in raised.value.issues] == ["name", "email", "password"]

    async def test_lists_admins_only(self, world: World) -> None:
        admins = await ListAdmins(world.state).execute()

        assert [admin.name.value for admin in admins] == ["Antonio", "Maria"]


class TestSeed:
    async def test_creates_the_first_admin_once(self, world: World) -> None:
        empty = InMemoryIdentityState()
        seed = SeedFirstAdmin(empty, world.hasher, world.clock)
        first = NewAccount(name="Administrator", email="admin@example.com", password=TEST_PASSWORD)

        created = await seed.execute(first)
        again = await seed.execute(
            NewAccount(name="Other", email="other@example.com", password=TEST_PASSWORD)
        )

        assert created is not None and created.role is Role.ADMIN
        assert again is None
        assert [account.email.value for account in empty.accounts.values()] == ["admin@example.com"]
        assert empty.events("account.created")[0].actor == "Seed"

    async def test_does_nothing_when_an_admin_exists(self, world: World) -> None:
        created = await SeedFirstAdmin(world.state, world.hasher, world.clock).execute(ANA)

        assert created is None
        assert world.state.account_by_email("ana@example.com") is None


class TestSignUp:
    def sign_up(self, world: World) -> SignUp:
        return SignUp(world.state, world.hasher, world.tokens, world.clock)

    async def test_creates_a_buyer_and_logs_them_in(self, world: World) -> None:
        result = await self.sign_up(world).execute(ANA)

        assert result.principal.role is Role.BUYER
        assert await world.authenticate().execute(result.token) == result.principal
        entry = world.state.events("account.created")[-1]
        assert (entry.actor, entry.context["source"]) == ("Ana Souza", "sign-up")

    async def test_never_takes_over_an_admins_email(self, world: World) -> None:
        before = world.state.account_by_email("antonio@example.com")

        with pytest.raises(EmailAlreadyRegistered):
            await self.sign_up(world).execute(
                NewAccount(name="Mallory", email="Antonio@Example.com", password=TEST_PASSWORD)
            )

        assert world.state.account_by_email("antonio@example.com") == before
        assert world.tokens.issued == 0
