"""
Pay2S Configuration
Store your Pay2S credentials and settings here.
For production, use environment variables or a secure config file.
"""
import os

# Payment provider selection
# Supported: "payos" | "pay2s"
# Default: PayOS (as requested)
PAYMENT_PROVIDER_DEFAULT = os.getenv("PAYMENT_PROVIDER_DEFAULT", "payos").lower()

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

# PayOS Configuration (Merchant API)
# Production base URL: https://api-merchant.payos.vn
PAYOS_BASE_URL = os.getenv("PAYOS_BASE_URL", "https://api-merchant.payos.vn")
PAYOS_PARTNER_CODE = os.getenv("PAYOS_PARTNER_CODE", "")
PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")# URLs used when creating payment links
PAYOS_RETURN_URL = os.getenv("PAYOS_RETURN_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))
PAYOS_CANCEL_URL = os.getenv("PAYOS_CANCEL_URL", os.getenv("REDIRECT_URL", "https://t.me/your_bot"))

# Support Contact Information (displayed in bot messages)
# You can customize both lines of the footer
SUPPORT_LINE_1 = os.getenv("SUPPORT_LINE_1", "🧑‍💻 Hỗ trợ: @muataikhoanpro")
SUPPORT_LINE_2 = os.getenv("SUPPORT_LINE_2", "📞 Zalo: 0964935727")
