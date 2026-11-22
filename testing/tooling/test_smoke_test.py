from types import ModuleType


def test_recognises_the_smoke_tests_own_product(smoke_test: ModuleType) -> None:
    product = dict(smoke_test.SMOKE_PRODUCT)

    assert smoke_test.is_owned_smoke_product(product)


def test_refuses_to_take_over_a_product_with_the_reserved_sku(smoke_test: ModuleType) -> None:
    product = {**smoke_test.SMOKE_PRODUCT, "name": "A merchant's product"}

    assert not smoke_test.is_owned_smoke_product(product)


def test_the_smoke_order_buys_only_the_smoke_product_with_a_declined_card(
    smoke_test: ModuleType,
) -> None:
    order = smoke_test.smoke_order()

    assert order["lines"] == [{"sku": smoke_test.SMOKE_SKU, "quantity": 1}]
    assert order["payment"]["card_number"] == "4000 0000 0000 0002"
