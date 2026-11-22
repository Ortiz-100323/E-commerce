from ecommerce.shared_kernel.domain.errors import DomainError


class InvalidCredentials(DomainError):
    def __init__(self) -> None:
        super().__init__("The email or password is incorrect.")


class TooManyLoginAttempts(DomainError):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Too many attempts. Try again in {retry_after_seconds} seconds.")


class EmailAlreadyRegistered(DomainError):
    def __init__(self) -> None:
        super().__init__("An account with this email already exists. Log in instead.")
