from collections.abc import Sequence
from uuid import UUID

from ecommerce.shared_kernel.domain.errors import DomainError, DomainValidationError, NotFoundError


class ImportNotFound(NotFoundError):
    def __init__(self, batch_id: UUID) -> None:
        self.batch_id = batch_id
        super().__init__("Import not found.")


class ImportRowNotFound(NotFoundError):
    def __init__(self, batch_id: UUID, line: int) -> None:
        self.batch_id = batch_id
        self.line = line
        super().__init__(f"Line {line} is not a row of this import.")


class ImportNotPending(DomainError):
    def __init__(self, batch_id: UUID, status: str) -> None:
        self.batch_id = batch_id
        self.status = status
        super().__init__(f"Import {batch_id} is {status} and can no longer be changed.")


class ImportRowNotResolvable(DomainError):
    def __init__(self, line: int, outcome: str, action: str) -> None:
        self.line = line
        self.outcome = outcome
        self.action = action
        super().__init__(f"Line {line} is {outcome}; it cannot be resolved with {action}.")


class ImportNotCommittable(DomainError):
    def __init__(self, pending_lines: Sequence[int]) -> None:
        self.pending_lines = tuple(pending_lines)
        super().__init__(f"{len(self.pending_lines)} row(s) still need a decision.")


class ImportStaleRows(DomainError):
    def __init__(self, lines: Sequence[int]) -> None:
        self.lines = tuple(lines)
        super().__init__(f"{len(self.lines)} row(s) changed in the catalog after the preview.")


class InvalidCorrection(DomainValidationError):
    pass
