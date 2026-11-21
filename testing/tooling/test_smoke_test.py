from types import ModuleType


def test_recognises_the_smoke_tests_own_product(smoke_test: ModuleType) -> None:
    product = dict(smoke_test.SMOKE_PRODUCT)

    assert smoke_test.is_owned_smoke_product(product)


def test_refuses_to_take_over_a_product_with_the_reserved_sku(smoke_test: ModuleType) -> None:
    product = {**smoke_test.SMOKE_PRODUCT, "name": "A merchant's product"}

    assert not smoke_test.is_owned_smoke_product(product)
