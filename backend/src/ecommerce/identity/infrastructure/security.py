import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field

SCHEME = "scrypt"
SALT_BYTES = 16
KEY_BYTES = 32
TOKEN_BYTES = 32


def encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


@dataclass(frozen=True)
class ScryptPasswordHasher:
    n: int = 2**15
    r: int = 8
    p: int = 3
    _dummy: list[str] = field(default_factory=list, repr=False, compare=False)

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(SALT_BYTES)
        key = self._derive(password, salt, self.n, self.r, self.p)
        return f"{SCHEME}${self.n}${self.r}${self.p}${encode(salt)}${encode(key)}"

    def verify(self, password: str, stored: str) -> bool:
        parsed = self._parse(stored)
        if parsed is None:
            return False
        n, r, p, salt, expected = parsed
        actual = self._derive(password, salt, n, r, p)
        return hmac.compare_digest(actual, expected)

    def needs_rehash(self, stored: str) -> bool:
        parsed = self._parse(stored)
        return parsed is None or parsed[:3] != (self.n, self.r, self.p)

    @property
    def dummy_hash(self) -> str:
        if not self._dummy:
            self._dummy.append(self.hash(secrets.token_urlsafe(16)))
        return self._dummy[0]

    def _derive(self, password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=KEY_BYTES,
            maxmem=128 * n * r * 2 + 1024 * 1024,
        )

    @staticmethod
    def _parse(stored: str) -> tuple[int, int, int, bytes, bytes] | None:
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != SCHEME:
            return None
        try:
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt, key = decode(parts[4]), decode(parts[5])
        except ValueError:
            return None
        if n < 2 or n & (n - 1) or r < 1 or p < 1 or n > 2**20 or not salt or not key:
            return None
        return n, r, p, salt, key


class SecretTokenSource:
    def new_token(self) -> str:
        return secrets.token_urlsafe(TOKEN_BYTES)
