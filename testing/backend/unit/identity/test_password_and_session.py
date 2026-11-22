from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ecommerce.identity.domain.password import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, Password
from ecommerce.identity.domain.session import (
    ABSOLUTE_LIFETIME,
    IDLE_TIMEOUT,
    TOUCH_EVERY,
    Session,
)
from ecommerce.identity.domain.throttle import MAX_FAILURES, WINDOW, retry_after
from ecommerce.shared_kernel.domain.errors import DomainValidationError

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
ACCOUNT = UUID("00000000-0000-4000-8000-0000000000a1")


class TestPassword:
    def test_accepts_12_to_128_characters_of_anything(self) -> None:
        assert Password("correct horse").value == "correct horse"
        assert Password("x" * MAX_PASSWORD_LENGTH).value == "x" * MAX_PASSWORD_LENGTH
        assert Password("ñandú-ñandú-ñ").value == "ñandú-ñandú-ñ"

    @pytest.mark.parametrize(
        ("raw", "code"),
        [
            ("", "required"),
            ("x" * (MIN_PASSWORD_LENGTH - 1), "too_short"),
            ("x" * (MAX_PASSWORD_LENGTH + 1), "too_long"),
        ],
    )
    def test_refuses_lengths_outside_the_rule(self, raw: str, code: str) -> None:
        with pytest.raises(DomainValidationError) as raised:
            Password(raw)

        assert [(issue.field, issue.code) for issue in raised.value.issues] == [("password", code)]

    def test_never_shows_itself(self) -> None:
        password = Password("correct horse battery")

        assert "correct horse" not in repr(password)
        assert "correct horse" not in str(password)

    def test_is_never_trimmed(self) -> None:
        assert Password("  twelve chars  ").value == "  twelve chars  "


class TestSession:
    def session(self) -> Session:
        return Session.start(session_id=ACCOUNT, account_id=ACCOUNT, token_hash="h", at=NOW)

    def test_is_active_until_30_idle_minutes_pass(self) -> None:
        session = self.session()

        assert session.is_active(NOW + IDLE_TIMEOUT - timedelta(seconds=1))
        assert not session.is_active(NOW + IDLE_TIMEOUT)

    def test_activity_keeps_it_alive_but_never_past_8_hours(self) -> None:
        session = self.session()
        moment = NOW
        while moment + timedelta(minutes=20) < NOW + ABSOLUTE_LIFETIME:
            moment += timedelta(minutes=20)
            assert session.is_active(moment)
            session = session.touched(moment)

        assert not session.is_active(NOW + ABSOLUTE_LIFETIME)

    def test_is_touched_at_most_once_a_minute(self) -> None:
        session = self.session()

        assert not session.needs_touch(NOW + TOUCH_EVERY - timedelta(seconds=1))
        assert session.needs_touch(NOW + TOUCH_EVERY)
        assert session.touched(NOW + TOUCH_EVERY).last_seen_at == NOW + TOUCH_EVERY


class TestThrottle:
    def test_allows_up_to_4_recent_failures(self) -> None:
        failures = [NOW - timedelta(minutes=minute) for minute in range(MAX_FAILURES - 1)]

        assert retry_after(failures, NOW) is None

    def test_refuses_the_sixth_attempt_until_the_oldest_failure_leaves_the_window(self) -> None:
        failures = [NOW - timedelta(minutes=10 - minute) for minute in range(MAX_FAILURES)]

        wait = retry_after(failures, NOW)

        assert wait == int((WINDOW - timedelta(minutes=10)).total_seconds())

    def test_forgets_failures_older_than_the_window(self) -> None:
        failures = [NOW - WINDOW - timedelta(seconds=1)] * 10 + [NOW] * (MAX_FAILURES - 1)

        assert retry_after(failures, NOW) is None

    def test_always_waits_at_least_one_second(self) -> None:
        failures = [NOW - WINDOW + timedelta(milliseconds=10)] * MAX_FAILURES

        assert retry_after(failures, NOW) == 1
