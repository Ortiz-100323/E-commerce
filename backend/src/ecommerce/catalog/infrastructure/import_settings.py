from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ecommerce.catalog.domain.importing.policies import (
    DEFAULT_MAX_ROWS,
    DEFAULT_SIMILARITY_THRESHOLD,
    CurrencySymbolPolicy,
    DuplicateSkuPolicy,
    EmptyFieldPolicy,
    ExistingSkuPolicy,
    ImportPolicies,
    SkuIdentityPolicy,
    ZeroPricePolicy,
    ZeroWeightPolicy,
)


class ImportSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMPORT_", extra="ignore")

    zero_price_policy: ZeroPricePolicy = ZeroPricePolicy.REVIEW_AS_GIFT
    empty_field_policy: EmptyFieldPolicy = EmptyFieldPolicy.REVIEW
    zero_weight_policy: ZeroWeightPolicy = ZeroWeightPolicy.REVIEW
    existing_sku_policy: ExistingSkuPolicy = ExistingSkuPolicy.UPDATE_WITH_CONFIRMATION
    duplicate_sku_in_file_policy: DuplicateSkuPolicy = DuplicateSkuPolicy.LAST_WINS
    currency_symbol_policy: CurrencySymbolPolicy = CurrencySymbolPolicy.STRIP_WITH_WARNING
    sku_identity_policy: SkuIdentityPolicy = SkuIdentityPolicy.NAME_SIMILARITY
    sku_similarity_threshold: float = Field(default=DEFAULT_SIMILARITY_THRESHOLD, gt=0, le=1)
    max_rows: int = Field(default=DEFAULT_MAX_ROWS, ge=1)

    def policies(self) -> ImportPolicies:
        return ImportPolicies(
            zero_price=self.zero_price_policy,
            empty_field=self.empty_field_policy,
            zero_weight=self.zero_weight_policy,
            existing_sku=self.existing_sku_policy,
            duplicate_sku=self.duplicate_sku_in_file_policy,
            currency_symbol=self.currency_symbol_policy,
            sku_identity=self.sku_identity_policy,
            similarity_threshold=self.sku_similarity_threshold,
            max_rows=self.max_rows,
        )
