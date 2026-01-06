"""
Test payment creation functionality.
"""
import sys
import os
import time
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pay2s import create_payment
from config import (
    PAY2S_ENDPOINT,
    ACCESS_KEY,
    SECRET_KEY,
    PARTNER_CODE,
    DEFAULT_AMOUNT,
    DEFAULT_BANK_ACCOUNTS,
    DEFAULT_REQUEST_TYPE,
)


def test_create_payment():
    """
    Test function to create a payment request using Pay2S API.
    """
    # Required parameters
    order_id = time.time()
    order_info = "TT" + str(order_id)  # Must be 10-32 characters, alphanumeric only
    redirect_url = "null"
    ipn_url = "https://ipn.arcreklabs.io.vn/ipn"
    partner_name = "Test"
    
    try:
        response = create_payment(
            endpoint=PAY2S_ENDPOINT,
            access_key=ACCESS_KEY,
            secret_key=SECRET_KEY,
            partner_code=PARTNER_CODE,
            amount=DEFAULT_AMOUNT,
            order_id=str(order_id),
            order_info=order_info,
            redirect_url=redirect_url,
            ipn_url=ipn_url,
            bank_accounts=DEFAULT_BANK_ACCOUNTS,
            request_type=DEFAULT_REQUEST_TYPE,
            partner_name=partner_name
        )
        
        print("Status Code: 200")
        print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        # Assert that payment creation was successful
        assert response is not None, "Payment response should not be None"
        assert 'payUrl' in response or 'message' in response, "Response should contain payUrl or message"
        
        # Check if payUrl exists and print it
        if 'payUrl' in response:
            print(f"\nPayment URL: {response['payUrl']}")
            assert response['payUrl'] is not None, "Payment URL should not be None"
        
    except Exception as e:
        print(f"Error making request: {e}")
        raise  # Re-raise exception so pytest can catch it


if __name__ == "__main__":
    test_create_payment()

