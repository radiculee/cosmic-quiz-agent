"""Draws the site's icons: a teal planet with a gold ring on the void colour, the same picture as
public/favicon.svg. Writes favicon.ico, apple-touch-icon.png, icon-192.png and icon-512.png into
public/. Needs nothing beyond the standard library; run `python -m dev.make_icons` after changing
the picture, and keep favicon.svg in step by hand."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"

VOID = (5, 5, 10)
TEAL = (78, 205, 196)
GOLD = (245, 230, 200)

Colour = tuple[int, int, int]

# The picture, as fractions of the icon's side.
PLANET_RADIUS = 0.30
RING_TILT = math.radians(-22)
RING_MAJOR, RING_MINOR = 0.44, 0.13
RING_WIDTH = 0.135  # in ring units: about 0.035 of the side across the minor axis
SAMPLES = 4  # per pixel side, for smooth edges


def _sample(x: float, y: float) -> Colour:
    """The colour at a point: the ring is behind the planet on one side."""
    dx, dy = x - 0.5, y - 0.5
    cos, sin = math.cos(-RING_TILT), math.sin(-RING_TILT)
    u, v = dx * cos - dy * sin, dx * sin + dy * cos  # the ring's own axes
    in_ring = abs(math.hypot(u / RING_MAJOR, v / RING_MINOR) - 1) < RING_WIDTH
    in_planet = math.hypot(dx, dy) < PLANET_RADIUS
    if in_ring and (v > 0 or not in_planet):
        return GOLD
    return TEAL if in_planet else VOID


def _pixel(px: int, py: int, size: int) -> Colour:
    total = [0, 0, 0]
    for i in range(SAMPLES):
        for j in range(SAMPLES):
            colour = _sample((px + (i + 0.5) / SAMPLES) / size, (py + (j + 0.5) / SAMPLES) / size)
            for channel in range(3):
                total[channel] += colour[channel]
    count = SAMPLES * SAMPLES
    return (total[0] // count, total[1] // count, total[2] // count)


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def png(size: int) -> bytes:
    """A square RGB PNG of the picture."""
    rows = bytearray()
    for py in range(size):
        rows.append(0)  # no filter
        for px in range(size):
            rows.extend(_pixel(px, py, size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def ico(size: int) -> bytes:
    """An ICO file holding one PNG image."""
    image = png(size)
    directory = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(image), 22)
    return directory + entry + image


def main() -> None:
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / "favicon.ico").write_bytes(ico(48))
    for name, size in (("apple-touch-icon.png", 180), ("icon-192.png", 192), ("icon-512.png", 512)):
        (PUBLIC / name).write_bytes(png(size))


if __name__ == "__main__":
    main()
