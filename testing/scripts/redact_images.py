import argparse
import struct
import sys
import zlib
from collections.abc import Sequence
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS_BY_COLOUR_TYPE = {2: 3, 6: 4}
COLOUR_TYPE_BY_CHANNELS = {3: 2, 4: 6}
DEFAULT_BLOCK = 12

type Pixel = tuple[int, ...]
type Box = tuple[int, int, int, int]


def chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(SIGNATURE):
        raise ValueError("The file is not a PNG image.")
    found = []
    offset = len(SIGNATURE)
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        found.append((kind, data[offset + 8 : offset + 8 + length]))
        offset += 12 + length
    return found


def paeth(left: int, up: int, corner: int) -> int:
    estimate = left + up - corner
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - corner))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    return up if distances[1] <= distances[2] else corner


def unfilter(raw: bytes, width: int, height: int, channels: int) -> list[bytearray]:
    stride = width * channels
    rows: list[bytearray] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        kind = raw[offset]
        line = bytearray(raw[offset + 1 : offset + 1 + stride])
        offset += 1 + stride
        for index in range(stride):
            left = line[index - channels] if index >= channels else 0
            up = previous[index]
            corner = previous[index - channels] if index >= channels else 0
            if kind == 1:
                line[index] = (line[index] + left) & 0xFF
            elif kind == 2:
                line[index] = (line[index] + up) & 0xFF
            elif kind == 3:
                line[index] = (line[index] + (left + up) // 2) & 0xFF
            elif kind == 4:
                line[index] = (line[index] + paeth(left, up, corner)) & 0xFF
            elif kind != 0:
                raise ValueError(f"Unknown PNG filter {kind}.")
        rows.append(line)
        previous = line
    return rows


def decode_png(data: bytes) -> tuple[int, int, int, list[list[Pixel]]]:
    found = chunks(data)
    header = next((body for kind, body in found if kind == b"IHDR"), None)
    if header is None:
        raise ValueError("The PNG image has no header.")
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", header)
    if depth != 8 or colour not in CHANNELS_BY_COLOUR_TYPE or interlace != 0:
        raise ValueError("Only 8-bit, non-interlaced RGB or RGBA PNG images are supported.")
    channels = CHANNELS_BY_COLOUR_TYPE[colour]
    raw = zlib.decompress(b"".join(body for kind, body in found if kind == b"IDAT"))
    rows = unfilter(raw, width, height, channels)
    pixels = [[tuple(row[x * channels : (x + 1) * channels]) for x in range(width)] for row in rows]
    return width, height, channels, pixels


def chunk(kind: bytes, body: bytes) -> bytes:
    checksum = zlib.crc32(kind + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", checksum)


def encode_png(width: int, height: int, channels: int, pixels: Sequence[Sequence[Pixel]]) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, COLOUR_TYPE_BY_CHANNELS[channels], 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(value for pixel in row for value in pixel) for row in pixels)
    return (
        SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def pixelate(pixels: list[list[Pixel]], box: Box, block: int) -> None:
    height = len(pixels)
    width = len(pixels[0]) if pixels else 0
    left, top = max(box[0], 0), max(box[1], 0)
    right, bottom = min(box[2], width), min(box[3], height)
    for block_top in range(top, bottom, block):
        for block_left in range(left, right, block):
            cells = [
                (y, x)
                for y in range(block_top, min(block_top + block, bottom))
                for x in range(block_left, min(block_left + block, right))
            ]
            channels = len(pixels[cells[0][0]][cells[0][1]])
            average = tuple(
                sum(pixels[y][x][channel] for y, x in cells) // len(cells)
                for channel in range(channels)
            )
            for y, x in cells:
                pixels[y][x] = average


def redact(path: Path, boxes: Sequence[Box], block: int = DEFAULT_BLOCK) -> None:
    width, height, channels, pixels = decode_png(path.read_bytes())
    for box in boxes:
        pixelate(pixels, box, block)
    path.write_bytes(encode_png(width, height, channels, pixels))


def parse_box(text: str) -> Box:
    left, top, right, bottom = (int(part) for part in text.split(","))
    if right <= left or bottom <= top:
        raise ValueError(f"The box {text} is empty.")
    return left, top, right, bottom


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Pixelate parts of PNG screenshots in place.")
    parser.add_argument("image", type=Path)
    parser.add_argument("boxes", nargs="*", help="left,top,right,bottom in pixels")
    parser.add_argument("--block", type=int, default=DEFAULT_BLOCK)
    arguments = parser.parse_args(argv)
    if not arguments.boxes:
        width, height, channels, _ = decode_png(arguments.image.read_bytes())
        print(f"{arguments.image}: {width}x{height}, {channels} channels")
        return 0
    redact(arguments.image, [parse_box(box) for box in arguments.boxes], arguments.block)
    print(f"redacted {arguments.image}: {len(arguments.boxes)} box(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
