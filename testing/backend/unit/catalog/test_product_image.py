from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ecommerce.catalog.domain.errors import InvalidProduct
from ecommerce.catalog.domain.events import FieldChange, ProductChanged, ProductCreated
from ecommerce.catalog.domain.product import Product, new_product_id
from ecommerce.catalog.domain.value_objects import MAX_IMAGE_URL_LENGTH, ImageUrl
from ecommerce.shared_kernel.domain.errors import DomainValidationError

AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
LATER = AT + timedelta(minutes=1)
PHOTO = "https://images.example.com/shoes/rs-001.jpg"


def shoes(image_url: str | None = None) -> Product:
    product = Product.create(
        product_id=new_product_id(),
        sku="RS-001",
        name="Running Shoes",
        description="",
        category="Sports",
        price=Decimal("89.99"),
        stock=10,
        weight_kg=Decimal("0.8"),
        gift=False,
        image_url=image_url,
        at=AT,
    )
    product.pull_events()
    return product


def test_an_https_image_url_is_kept_trimmed() -> None:
    assert ImageUrl(f"  {PHOTO}  ").value == PHOTO


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("http://images.example.com/a.jpg", "image_url_not_https"),
        ("javascript:alert(1)", "image_url_not_https"),
        ("data:image/png;base64,AAAA", "image_url_not_https"),
        ("//images.example.com/a.jpg", "image_url_not_https"),
        ("https://", "invalid_image_url"),
        ("https:///no-host.jpg", "invalid_image_url"),
        ("https://[invalid-ipv6/photo.jpg", "invalid_image_url"),
        ("https://images.example.com:bad/photo.jpg", "invalid_image_url"),
        ("https://images.example.com:99999/photo.jpg", "invalid_image_url"),
        ("https://images.example.com/a b.jpg", "invalid_image_url"),
        ("https://images.example.com/a\tb.jpg", "invalid_image_url"),
        ("https://images.example.com/" + "a" * MAX_IMAGE_URL_LENGTH, "too_long"),
    ],
)
def test_an_image_url_must_be_a_plain_https_address(value: str, code: str) -> None:
    with pytest.raises(DomainValidationError) as error:
        ImageUrl(value)

    assert [(issue.field, issue.code) for issue in error.value.issues] == [("image_url", code)]


def test_of_treats_an_empty_value_as_no_image() -> None:
    assert ImageUrl.of("   ") is None
    assert ImageUrl.of(PHOTO) == ImageUrl(PHOTO)


def test_a_product_is_created_with_or_without_an_image() -> None:
    with_image = Product.create(
        product_id=new_product_id(),
        sku="RS-001",
        name="Running Shoes",
        description="",
        category="Sports",
        price=Decimal("89.99"),
        stock=10,
        weight_kg=Decimal("0.8"),
        gift=False,
        image_url=PHOTO,
        at=AT,
    )

    created = with_image.pull_events()[0]
    assert isinstance(created, ProductCreated)
    assert created.snapshot["image_url"] == PHOTO
    assert with_image.image_url == ImageUrl(PHOTO)
    assert shoes().image_url is None


def test_setting_an_image_records_the_change() -> None:
    product = shoes()

    product.revise(image_url=PHOTO, at=LATER)

    events = product.pull_events()
    assert len(events) == 1
    changed = events[0]
    assert isinstance(changed, ProductChanged)
    assert changed.changes == {"image_url": FieldChange(None, PHOTO)}


def test_an_empty_value_clears_the_image_and_none_keeps_it() -> None:
    product = shoes(PHOTO)

    product.revise(name="Trail Shoes", at=LATER)
    assert product.image_url == ImageUrl(PHOTO)
    product.revise(image_url="", at=LATER)

    assert product.image_url is None
    changes = [
        event.changes for event in product.pull_events() if isinstance(event, ProductChanged)
    ]
    assert changes[-1] == {"image_url": FieldChange(PHOTO, None)}


def test_the_same_image_records_nothing() -> None:
    product = shoes(PHOTO)

    product.revise(image_url=f" {PHOTO} ", at=LATER)

    assert product.pull_events() == []


def test_an_invalid_image_is_reported_with_the_other_problems() -> None:
    product = shoes()

    with pytest.raises(InvalidProduct) as error:
        product.revise(name="", image_url="http://insecure.example.com/a.jpg", at=LATER)

    assert sorted(issue.field for issue in error.value.issues) == ["image_url", "name"]


def test_the_scheme_is_stored_in_lower_case() -> None:
    assert ImageUrl("HTTPS://Images.example.com/A.jpg").value == "https://Images.example.com/A.jpg"
