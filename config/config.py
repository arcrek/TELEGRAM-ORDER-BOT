"""
Pay2S Configuration
Store your Pay2S credentials and settings here.
For production, use environment variables or a secure config file.
"""
import os

# Pay2S API Configuration
# Sandbox: https://sandbox-payment.pay2s.vn/v1/gateway/api/create
# Production: https://payment.pay2s.vn/v1/gateway/api/create
PAY2S_ENDPOINT = os.getenv(
    "PAY2S_ENDPOINT",
    "https://sandbox-payment.pay2s.vn/v1/gateway/api/create"
)

# Pay2S Credentials
PARTNER_CODE = os.getenv(
    "PAY2S_PARTNER_CODE",
    "PAY2S7EPF0SB1ZP27W71"
)

ACCESS_KEY = os.getenv(
    "PAY2S_ACCESS_KEY",
    "REDACTED_PAY2S_ACCESS_KEY"
)

SECRET_KEY = os.getenv(
    "PAY2S_SECRET_KEY",
    "REDACTED_PAY2S_SECRET_KEY"
)

# Default Payment Settings
DEFAULT_REQUEST_TYPE = "pay2s"
DEFAULT_AMOUNT = 100000
DEFAULT_BANK_ACCOUNTS = [
    {
        "account_number": "99999999",
        "bank_id": "ACB"
    }
]

# IPN Server Configuration
IPN_HOST = os.getenv("IPN_HOST", "0.0.0.0")
IPN_PORT = int(os.getenv("IPN_PORT", "5001"))

