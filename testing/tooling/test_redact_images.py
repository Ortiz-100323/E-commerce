from pathlib import Path
from types import ModuleType

import pytest

WIDTH = 40
HEIGHT = 30


def pattern(x: int, y: int) -> tuple[int, ...]:
    return ((x * 37) % 256, (y * 53) % 256, ((x + y) * 11) % 256, 255)


def write_sample(module: ModuleType, path: Path, channels: int) -> None:
    pixels = [[pattern(x, y)[:channels] for x in range(WIDTH)] for y in range(HEIGHT)]
    path.write_bytes(module.encode_png(WIDTH, HEIGHT, channels, pixels))


@pytest.mark.parametrize("channels", [3, 4])
def test_pixelates_only_the_given_box(
    redact_images: ModuleType, tmp_path: Path, channels: int
) -> None:
    image = tmp_path / "shot.png"
    write_sample(redact_images, image, channels)

    redact_images.redact(image, [(10, 5, 30, 20)], block=5)

    width, height, found, pixels = redact_images.decode_png(image.read_bytes())
    assert (width, height, found) == (WIDTH, HEIGHT, channels)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            inside = 10 <= x < 30 and 5 <= y < 20
            if not inside:
                assert pixels[y][x] == pattern(x, y)[:channels]
    for top in range(5, 20, 5):
        for left in range(10, 30, 5):
            block = {pixels[y][x] for y in range(top, top + 5) for x in range(left, left + 5)}
            assert len(block) == 1
    assert pixels[5][10] != pattern(10, 5)[:channels]


def test_a_box_is_clipped_to_the_image(redact_images: ModuleType, tmp_path: Path) -> None:
    image = tmp_path / "shot.png"
    write_sample(redact_images, image, 4)

    redact_images.redact(image, [(35, 25, 400, 300)], block=4)

    width, height, _, pixels = redact_images.decode_png(image.read_bytes())
    assert (width, height) == (WIDTH, HEIGHT)
    assert len({pixels[y][x] for y in range(25, 29) for x in range(35, 39)}) == 1


def test_parses_boxes_from_the_command_line(redact_images: ModuleType) -> None:
    assert redact_images.parse_box("10,20,110,48") == (10, 20, 110, 48)
    with pytest.raises(ValueError):
        redact_images.parse_box("10,20,5,48")


def test_refuses_formats_it_does_not_handle(redact_images: ModuleType) -> None:
    with pytest.raises(ValueError, match="PNG"):
        redact_images.decode_png(b"not a png")
