from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ecommerce.catalog.domain.errors import InsufficientStock, InvalidProduct, ProductNotSellable
from ecommerce.catalog.domain.events import (
    FieldChange,
    ProductArchived,
    ProductChanged,
    ProductCreated,
    ProductRestored,
    StockDecreased,
)
from ecommerce.catalog.domain.product import (
    INITIAL_VERSION,
    Product,
    ProductDetails,
    ProductId,
    ProductStatus,
    new_product_id,
)
from ecommerce.catalog.domain.value_objects import (
    MAX_STOCK,
    Category,
    Description,
    Price,
    ProductName,
    ProductTag,
    Sku,
    StockQuantity,
    Weight,
)

PRODUCT_ID = ProductId(UUID("00000000-0000-4000-8000-000000000001"))
CREATED_AT = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
LATER = CREATED_AT + timedelta(hours=1)
BOOL_VALUE: Any = True


def create(**overrides: Any) -> Product:
    values: dict[str, Any] = {
        "product_id": PRODUCT_ID,
        "sku": "rs-001",
        "name": "Running Shoes",
        "description": "Lightweight shoes.",
        "category": "Sports",
        "price": "89.99",
        "stock": 10,
        "weight_kg": "0.800",
        "gift": False,
        "at": CREATED_AT,
    }
    values.update(overrides)
    return Product.create(**values)


def existing(**overrides: Any) -> Product:
    product = create(**overrides)
    product.pull_events()
    return product


def codes_by_field(error: InvalidProduct) -> dict[str, str]:
    return {issue.field: issue.code for issue in error.issues}


def test_new_product_ids_are_unique_uuids() -> None:
    assert new_product_id() != new_product_id()
    assert isinstance(new_product_id(), UUID)


def test_create_builds_an_active_product_from_raw_values() -> None:
    product = create()

    assert product.id == PRODUCT_ID
    assert product.sku == Sku("RS-001")
    assert product.name == ProductName("Running Shoes")
    assert product.description == Description("Lightweight shoes.")
    assert product.category == Category("Sports")
    assert product.price == Price.of("89.99")
    assert product.stock == StockQuantity(10)
    assert product.weight == Weight.of("0.8")
    assert product.tags == frozenset()
    assert not product.is_gift
    assert product.status is ProductStatus.ACTIVE
    assert product.version == INITIAL_VERSION
    assert product.created_at == CREATED_AT
    assert product.updated_at == CREATED_AT


def test_create_records_product_created_with_a_snapshot() -> None:
    product = create()

    assert product.pull_events() == [
        ProductCreated(
            product_id=PRODUCT_ID,
            sku="RS-001",
            occurred_at=CREATED_AT,
            snapshot={
                "sku": "RS-001",
                "name": "Running Shoes",
                "description": "Lightweight shoes.",
                "category": "Sports",
                "price": "89.99",
                "stock": 10,
                "weight_kg": "0.800",
                "tags": (),
                "status": "ACTIVE",
            },
        )
    ]


def test_pull_events_empties_the_list() -> None:
    product = create()
    product.pull_events()
    assert product.pull_events() == []


def test_create_reports_every_invalid_field_at_once() -> None:
    with pytest.raises(InvalidProduct) as raised:
        create(
            sku="bad sku",
            name="<b>Shoes</b>",
            description="Tab\there",
            category=" ",
            price="-1",
            stock=-5,
            weight_kg="heavy",
        )

    assert codes_by_field(raised.value) == {
        "sku": "invalid_sku_format",
        "name": "markup_not_allowed",
        "description": "control_characters_not_allowed",
        "category": "required",
        "price": "too_small",
        "stock": "too_small",
        "weight_kg": "not_a_number",
    }


def test_a_zero_price_without_the_gift_tag_is_rejected() -> None:
    with pytest.raises(InvalidProduct) as raised:
        create(price="0.00")
    assert codes_by_field(raised.value) == {"price": "zero_price_requires_gift"}


def test_the_gift_rule_is_reported_together_with_other_issues() -> None:
    with pytest.raises(InvalidProduct) as raised:
        create(price="0", name="")
    assert codes_by_field(raised.value) == {"name": "required", "price": "zero_price_requires_gift"}


def test_a_zero_price_with_the_gift_tag_is_allowed() -> None:
    product = create(price="0", gift=True)
    assert product.is_gift
    assert product.tags == frozenset({ProductTag.GIFT})
    assert product.price.is_zero


def test_a_paid_product_may_also_be_a_gift() -> None:
    assert create(price="10", gift=True).is_gift


def test_product_details_refuse_a_zero_price_without_the_gift_tag() -> None:
    with pytest.raises(InvalidProduct) as raised:
        ProductDetails(
            name=ProductName("Mug"),
            description=Description(""),
            category=Category("Home"),
            price=Price.of("0"),
            stock=StockQuantity(1),
            weight=Weight.of("0.3"),
            tags=frozenset(),
        )
    assert codes_by_field(raised.value) == {"price": "zero_price_requires_gift"}


def test_rename_records_one_change_with_before_and_after() -> None:
    product = existing()

    product.rename(" Trail Shoes ", at=LATER)

    assert product.name == ProductName("Trail Shoes")
    assert product.updated_at == LATER
    assert product.pull_events() == [
        ProductChanged(
            product_id=PRODUCT_ID,
            sku="RS-001",
            occurred_at=LATER,
            changes={"name": FieldChange("Running Shoes", "Trail Shoes")},
        )
    ]


def test_an_invalid_rename_changes_nothing() -> None:
    product = existing()

    with pytest.raises(InvalidProduct) as raised:
        product.rename("<script>", at=LATER)

    assert codes_by_field(raised.value) == {"name": "markup_not_allowed"}
    assert product.name == ProductName("Running Shoes")
    assert product.updated_at == CREATED_AT
    assert product.pull_events() == []


def test_a_change_to_the_same_value_records_nothing() -> None:
    product = existing()

    product.rename("  Running Shoes ", at=LATER)
    product.reprice("89.990", at=LATER)

    assert product.updated_at == CREATED_AT
    assert product.pull_events() == []


def test_reprice_records_one_change() -> None:
    product = existing()

    product.reprice(Decimal("79.5"), at=LATER)

    assert product.price == Price.of("79.50")
    assert product.pull_events()[0] == ProductChanged(
        product_id=PRODUCT_ID,
        sku="RS-001",
        occurred_at=LATER,
        changes={"price": FieldChange("89.99", "79.50")},
    )


def test_reprice_to_zero_requires_the_gift_tag() -> None:
    product = existing()

    with pytest.raises(InvalidProduct) as raised:
        product.reprice("0", at=LATER)

    assert codes_by_field(raised.value) == {"price": "zero_price_requires_gift"}
    assert product.price == Price.of("89.99")


def test_reprice_to_zero_is_allowed_for_a_gift() -> None:
    product = existing(gift=True)
    product.reprice("0", at=LATER)
    assert product.price.is_zero


def test_recategorize_records_one_change() -> None:
    product = existing()

    product.recategorize("Outdoor", at=LATER)

    assert product.category == Category("Outdoor")
    assert product.pull_events()[0].changes == {"category": FieldChange("Sports", "Outdoor")}


def test_recategorize_to_another_spelling_of_the_same_category_keeps_the_original() -> None:
    product = existing()

    product.recategorize("SPORTS", at=LATER)

    assert product.category.value == "Sports"
    assert product.pull_events() == []


def test_restock_adds_to_the_stock_and_records_one_change() -> None:
    product = existing()

    product.restock(5, at=LATER)

    assert product.stock == StockQuantity(15)
    assert product.pull_events()[0].changes == {"stock": FieldChange(10, 15)}


@pytest.mark.parametrize("quantity", [0, -3])
def test_restock_needs_a_positive_quantity(quantity: int) -> None:
    product = existing()

    with pytest.raises(InvalidProduct) as raised:
        product.restock(quantity, at=LATER)

    assert raised.value.issues[0].field == "quantity"
    assert raised.value.issues[0].code == "too_small"
    assert raised.value.issues[0].params == {"min": 1}
    assert product.stock == StockQuantity(10)


def test_restock_cannot_go_beyond_the_maximum_stock() -> None:
    product = existing(stock=MAX_STOCK)

    with pytest.raises(InvalidProduct) as raised:
        product.restock(1, at=LATER)

    assert codes_by_field(raised.value) == {"stock": "too_large"}


def test_restock_rejects_quantities_that_are_not_whole_numbers() -> None:
    with pytest.raises(TypeError):
        existing().restock(BOOL_VALUE, at=LATER)


def test_mark_as_gift_records_one_change() -> None:
    product = existing()

    product.mark_as_gift(at=LATER)

    assert product.is_gift
    assert product.pull_events()[0].changes == {"tags": FieldChange((), ("GIFT",))}


def test_mark_as_gift_on_a_gift_records_nothing() -> None:
    product = existing(gift=True)
    product.mark_as_gift(at=LATER)
    assert product.pull_events() == []


def test_unmark_gift_records_one_change() -> None:
    product = existing(gift=True)

    product.unmark_gift(at=LATER)

    assert not product.is_gift
    assert product.pull_events()[0].changes == {"tags": FieldChange(("GIFT",), ())}


def test_the_gift_tag_cannot_be_removed_while_the_price_is_zero() -> None:
    product = existing(price="0", gift=True)

    with pytest.raises(InvalidProduct) as raised:
        product.unmark_gift(at=LATER)

    assert codes_by_field(raised.value) == {"gift": "zero_price_requires_gift"}
    assert product.is_gift


def test_revise_changes_several_fields_in_one_event() -> None:
    product = existing(price="0", gift=True)

    product.revise(
        name="Trail Shoes",
        description="Grippy soles.",
        category="Outdoor",
        price="99.00",
        stock=3,
        weight_kg="1",
        gift=False,
        at=LATER,
    )

    assert product.pull_events() == [
        ProductChanged(
            product_id=PRODUCT_ID,
            sku="RS-001",
            occurred_at=LATER,
            changes={
                "name": FieldChange("Running Shoes", "Trail Shoes"),
                "description": FieldChange("Lightweight shoes.", "Grippy soles."),
                "category": FieldChange("Sports", "Outdoor"),
                "price": FieldChange("0.00", "99.00"),
                "stock": FieldChange(10, 3),
                "weight_kg": FieldChange("0.800", "1.000"),
                "tags": FieldChange(("GIFT",), ()),
            },
        )
    ]


def test_revise_only_records_the_fields_that_changed() -> None:
    product = existing()

    product.revise(name="Running Shoes", price="95", at=LATER)

    assert product.pull_events()[0].changes == {"price": FieldChange("89.99", "95.00")}


def test_revise_reports_every_invalid_field_and_changes_nothing() -> None:
    product = existing()

    with pytest.raises(InvalidProduct) as raised:
        product.revise(name="", stock=-1, weight_kg="1.2345", at=LATER)

    assert codes_by_field(raised.value) == {
        "name": "required",
        "stock": "too_small",
        "weight_kg": "too_many_decimal_places",
    }
    assert product.name == ProductName("Running Shoes")
    assert product.pull_events() == []


def test_revise_can_set_a_zero_price_and_the_gift_tag_together() -> None:
    product = existing()

    product.revise(price="0", gift=True, at=LATER)

    assert product.price.is_zero
    assert product.is_gift


def test_decrease_stock_records_stock_decreased_with_the_order_reference() -> None:
    product = existing()

    product.decrease_stock(4, order_reference="order-1", at=LATER)

    assert product.stock == StockQuantity(6)
    assert product.updated_at == LATER
    assert product.pull_events() == [
        StockDecreased(
            product_id=PRODUCT_ID,
            sku="RS-001",
            occurred_at=LATER,
            quantity=4,
            stock_before=10,
            stock_after=6,
            order_reference="order-1",
        )
    ]


def test_decrease_stock_may_sell_the_last_unit() -> None:
    product = existing(stock=2)
    product.decrease_stock(2, order_reference="order-1", at=LATER)
    assert product.stock.is_empty
    assert not product.is_sellable


def test_decrease_stock_beyond_the_available_stock_raises_insufficient_stock() -> None:
    product = existing(stock=3)

    with pytest.raises(InsufficientStock) as raised:
        product.decrease_stock(4, order_reference="order-1", at=LATER)

    assert (raised.value.sku, raised.value.requested, raised.value.available) == ("RS-001", 4, 3)
    assert product.stock == StockQuantity(3)
    assert product.pull_events() == []


@pytest.mark.parametrize("quantity", [0, -1])
def test_decrease_stock_needs_a_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValueError):
        existing().decrease_stock(quantity, order_reference="order-1", at=LATER)


def test_decrease_stock_rejects_quantities_that_are_not_whole_numbers() -> None:
    with pytest.raises(TypeError):
        existing().decrease_stock(BOOL_VALUE, order_reference="order-1", at=LATER)


def test_an_archived_product_cannot_lose_stock() -> None:
    product = existing()
    product.archive(at=LATER)
    product.pull_events()

    with pytest.raises(ProductNotSellable) as raised:
        product.decrease_stock(1, order_reference="order-1", at=LATER)

    assert (raised.value.sku, raised.value.reason) == ("RS-001", "archived")
    assert product.stock == StockQuantity(10)


@given(
    stock=st.integers(min_value=0, max_value=500),
    moves=st.lists(
        st.tuples(st.sampled_from(["sell", "restock"]), st.integers(min_value=1, max_value=300)),
        max_size=30,
    ),
)
def test_stock_never_goes_below_zero(stock: int, moves: list[tuple[str, int]]) -> None:
    product = existing(stock=stock)
    expected = stock

    for move, quantity in moves:
        if move == "restock":
            product.restock(quantity, at=LATER)
            expected += quantity
        elif quantity <= expected:
            product.decrease_stock(quantity, order_reference="order-1", at=LATER)
            expected -= quantity
        else:
            with pytest.raises(InsufficientStock):
                product.decrease_stock(quantity, order_reference="order-1", at=LATER)
        assert product.stock.value == expected >= 0


def test_archive_records_product_archived() -> None:
    product = existing()

    product.archive(at=LATER)

    assert product.status is ProductStatus.ARCHIVED
    assert product.updated_at == LATER
    assert product.pull_events() == [
        ProductArchived(product_id=PRODUCT_ID, sku="RS-001", occurred_at=LATER)
    ]


def test_archiving_an_archived_product_records_nothing() -> None:
    product = existing()
    product.archive(at=LATER)
    product.pull_events()

    product.archive(at=LATER + timedelta(hours=1))

    assert product.updated_at == LATER
    assert product.pull_events() == []


def test_restore_records_product_restored() -> None:
    product = existing()
    product.archive(at=LATER)
    product.pull_events()
    restored_at = LATER + timedelta(hours=1)

    product.restore(at=restored_at)

    assert product.status is ProductStatus.ACTIVE
    assert product.pull_events() == [
        ProductRestored(product_id=PRODUCT_ID, sku="RS-001", occurred_at=restored_at)
    ]


def test_restoring_an_active_product_records_nothing() -> None:
    product = existing()
    product.restore(at=LATER)
    assert product.pull_events() == []


def test_an_archived_product_can_still_be_edited() -> None:
    product = existing()
    product.archive(at=LATER)
    product.pull_events()

    product.reprice("80", at=LATER)

    assert product.price == Price.of("80")


@pytest.mark.parametrize(
    ("stock", "archived", "sellable"),
    [(5, False, True), (0, False, False), (5, True, False), (0, True, False)],
)
def test_a_product_is_sellable_only_when_active_and_in_stock(
    stock: int, archived: bool, sellable: bool
) -> None:
    product = existing(stock=stock)
    if archived:
        product.archive(at=LATER)
    assert product.is_sellable is sellable


def test_a_product_can_be_rebuilt_from_stored_state_without_events() -> None:
    product = Product(
        product_id=PRODUCT_ID,
        sku=Sku("RS-001"),
        details=ProductDetails(
            name=ProductName("Running Shoes"),
            description=Description(""),
            category=Category("Sports"),
            price=Price.of("89.99"),
            stock=StockQuantity(10),
            weight=Weight.of("0.8"),
            tags=frozenset(),
        ),
        status=ProductStatus.ARCHIVED,
        version=7,
        created_at=CREATED_AT,
        updated_at=LATER,
    )

    assert product.version == 7
    assert product.status is ProductStatus.ARCHIVED
    assert product.pull_events() == []


def test_bump_version_moves_to_the_next_version_without_events() -> None:
    product = existing()

    product.bump_version()

    assert product.version == INITIAL_VERSION + 1
    assert product.pull_events() == []


def test_changes_do_not_alter_the_version() -> None:
    product = existing()
    product.rename("Trail Shoes", at=LATER)
    product.decrease_stock(1, order_reference="order-1", at=LATER)
    product.archive(at=LATER)
    assert product.version == INITIAL_VERSION
