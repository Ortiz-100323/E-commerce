from dataclasses import dataclass
from enum import StrEnum

DEFAULT_SIMILARITY_THRESHOLD = 0.5
DEFAULT_MAX_ROWS = 10_000


class ZeroPricePolicy(StrEnum):
    REVIEW_AS_GIFT = "review_as_gift"
    REJECT = "reject"
    ACCEPT_AS_GIFT = "accept_as_gift"


class EmptyFieldPolicy(StrEnum):
    REVIEW = "review"
    REJECT = "reject"


class ZeroWeightPolicy(StrEnum):
    REVIEW = "review"
    ACCEPT = "accept"
    REJECT = "reject"


class ExistingSkuPolicy(StrEnum):
    UPDATE_WITH_CONFIRMATION = "update_with_confirmation"
    CREATE_ONLY = "create_only"
    UPDATE_SILENTLY = "update_silently"


class DuplicateSkuPolicy(StrEnum):
    LAST_WINS = "last_wins"
    FIRST_WINS = "first_wins"
    REJECT_ALL = "reject_all"


class CurrencySymbolPolicy(StrEnum):
    STRIP_WITH_WARNING = "strip_with_warning"
    REJECT = "reject"


class SkuIdentityPolicy(StrEnum):
    NAME_SIMILARITY = "name_similarity"
    EXACT_NAME = "exact_name"
    SKU_ONLY = "sku_only"


@dataclass(frozen=True, kw_only=True)
class ImportPolicies:
    zero_price: ZeroPricePolicy = ZeroPricePolicy.REVIEW_AS_GIFT
    empty_field: EmptyFieldPolicy = EmptyFieldPolicy.REVIEW
    zero_weight: ZeroWeightPolicy = ZeroWeightPolicy.REVIEW
    existing_sku: ExistingSkuPolicy = ExistingSkuPolicy.UPDATE_WITH_CONFIRMATION
    duplicate_sku: DuplicateSkuPolicy = DuplicateSkuPolicy.LAST_WINS
    currency_symbol: CurrencySymbolPolicy = CurrencySymbolPolicy.STRIP_WITH_WARNING
    sku_identity: SkuIdentityPolicy = SkuIdentityPolicy.NAME_SIMILARITY
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    max_rows: int = DEFAULT_MAX_ROWS

    def __post_init__(self) -> None:
        if not 0 < self.similarity_threshold <= 1:
            raise ValueError("The similarity threshold must be above 0 and at most 1.")
        if self.max_rows < 1:
            raise ValueError("The row limit must be at least 1.")
