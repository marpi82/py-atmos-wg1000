"""CRC-32 used on every WG1000 WebSocket frame."""

from __future__ import annotations

import zlib

_CRC_MASK = 0xFFFFFFFF


def frame_crc(data: bytes) -> int:
    """Return the CRC stored after ``data``.

    The gateway UI builds a reflected CRC-32 (the same polynomial, init, and
    xor-out as :func:`zlib.crc32`) and then stores the bitwise complement.
    A complete frame therefore satisfies ``zlib.crc32(frame) == 0xFFFFFFFF``.

    Args:
        data: Frame bytes without the trailing CRC.

    Returns:
        Unsigned 32-bit residue to append, little-endian.
    """
    return (~zlib.crc32(data)) & _CRC_MASK


def frame_crc_ok(frame: bytes) -> bool:
    """Return whether ``frame`` includes a valid trailing CRC.

    Args:
        frame: Complete frame, including the four CRC bytes.

    Returns:
        True when the zlib CRC-32 of the whole frame is ``0xFFFFFFFF``.
    """
    if len(frame) < 4:
        return False
    return (zlib.crc32(frame) & _CRC_MASK) == _CRC_MASK
