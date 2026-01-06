"""
Configuration module for Pay2S integration.
"""
from .config import (
    PAY2S_ENDPOINT,
    PARTNER_CODE,
    ACCESS_KEY,
    SECRET_KEY,
    DEFAULT_REQUEST_TYPE,
    DEFAULT_AMOUNT,
    DEFAULT_BANK_ACCOUNTS,
    IPN_HOST,
    IPN_PORT,
)

__all__ = [
    "PAY2S_ENDPOINT",
    "PARTNER_CODE",
    "ACCESS_KEY",
    "SECRET_KEY",
    "DEFAULT_REQUEST_TYPE",
    "DEFAULT_AMOUNT",
    "DEFAULT_BANK_ACCOUNTS",
    "IPN_HOST",
    "IPN_PORT",
]

