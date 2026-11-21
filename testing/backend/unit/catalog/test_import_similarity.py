import pytest

from ecommerce.catalog.domain.importing.policies import SkuIdentityPolicy
from ecommerce.catalog.domain.importing.similarity import (
    normalize_name,
    same_product,
    similarity,
    trigrams,
)


def test_names_are_normalised_with_nfkc_casefold_and_single_spaces() -> None:
    assert normalize_name("  Running   SHOES ") == "running shoes"
    assert normalize_name("Ｒｕｎｎｉｎｇ") == "running"
    assert normalize_name("Straße") == "strasse"


def test_trigrams_follow_pg_trgm_padding() -> None:
    assert trigrams("cat") == {"  c", " ca", "cat", "at "}
    assert trigrams("") == set()


def test_similarity_matches_postgres_pg_trgm_values() -> None:
    assert similarity("word", "two words") == pytest.approx(0.363636, abs=1e-6)
    assert similarity("Running Shoes", "Running Shoes") == 1.0
    assert similarity("", "") == 0.0


@pytest.mark.parametrize(
    ("catalog", "row", "expected"),
    [
        ("Running Shoes", "running  shoes", True),
        ("Running Shoes", "Running Shoes Pro", True),
        ("Running Shoes", "Yoga Mat", False),
        ("Cotton T-Shirt", "Organic Tee", False),
    ],
)
def test_name_similarity_identity_uses_the_threshold(
    catalog: str, row: str, expected: bool
) -> None:
    assert same_product(catalog, row, SkuIdentityPolicy.NAME_SIMILARITY, 0.5) is expected


def test_exact_name_identity_accepts_only_the_same_normalised_name() -> None:
    assert same_product("Running Shoes", "RUNNING shoes", SkuIdentityPolicy.EXACT_NAME, 0.5)
    assert not same_product("Running Shoes", "Running Shoes Pro", SkuIdentityPolicy.EXACT_NAME, 0.5)


def test_sku_only_identity_never_checks_the_name() -> None:
    assert same_product("Running Shoes", "Yoga Mat", SkuIdentityPolicy.SKU_ONLY, 0.5)
