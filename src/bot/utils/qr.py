"""
QR code utilities for Telegram bot.
"""

from __future__ import annotations

from io import BytesIO


def make_qr_png_bytes(data: str) -> BytesIO:
    """
    Create a PNG image (BytesIO) for a given QR payload string.
    """
    import qrcode

    img = qrcode.make(data)
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    bio.name = "qr.png"
    return bio

