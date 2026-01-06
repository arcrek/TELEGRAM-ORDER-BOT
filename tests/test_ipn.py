"""
Test IPN processing functionality.
"""
import sys
import os
import time
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pay2s import generate_ipn_signature, verify_ipn_signature
from config import (
    ACCESS_KEY,
    SECRET_KEY,
    PARTNER_CODE,
    DEFAULT_AMOUNT,
)


def test_process_ipn():
    """
    Test function to process an IPN notification from Pay2S.
    This simulates receiving an IPN callback and verifies it.
    """
    # Sample IPN data (as would be received from Pay2S)
    sample_ipn_data = {
        "partnerCode": PARTNER_CODE,
        "orderId": "1766804101.015664",
        "requestId": "1766804101.015664",
        "amount": DEFAULT_AMOUNT,
        "orderInfo": "Test Thue 1234556",
        "orderType": "Pay2S_wallet",
        "transId": 2588659987,
        "resultCode": 0,
        "message": "Giao dịch thành công.",
        "payType": "qr",
        "accessKey": ACCESS_KEY,
        "extraData": "",
        "responseTime": int(time.time() * 1000),  # milliseconds timestamp
        "signature": ""  # Will be generated for testing
    }
    
    # Generate signature for the sample IPN data
    sample_ipn_data['signature'] = generate_ipn_signature(
        access_key=sample_ipn_data['accessKey'],
        amount=sample_ipn_data['amount'],
        extra_data=sample_ipn_data.get('extraData', ''),
        message=sample_ipn_data['message'],
        order_id=sample_ipn_data['orderId'],
        order_info=sample_ipn_data['orderInfo'],
        order_type=sample_ipn_data['orderType'],
        partner_code=sample_ipn_data['partnerCode'],
        pay_type=sample_ipn_data['payType'],
        request_id=sample_ipn_data['requestId'],
        response_time=str(sample_ipn_data['responseTime']),
        result_code=str(sample_ipn_data['resultCode']),
        trans_id=str(sample_ipn_data['transId']),
        secret_key=SECRET_KEY
    )
    
    print("=" * 60)
    print("Testing IPN Processing")
    print("=" * 60)
    print("\nReceived IPN Data:")
    print(json.dumps(sample_ipn_data, indent=2, ensure_ascii=False))
    
    # Verify signature
    is_valid, partner_signature, debug_info = verify_ipn_signature(sample_ipn_data, SECRET_KEY)
    
    print(f"\n{'=' * 60}")
    print("Signature Verification")
    print(f"{'=' * 60}")
    print(f"Valid: {is_valid}")
    print("\nDebug Info:")
    print(f"Raw Hash: {debug_info.get('rawHash', 'N/A')}")
    print(f"Pay2S Signature: {debug_info.get('pay2sSignature', 'N/A')}")
    print(f"Partner Signature: {debug_info.get('partnerSignature', 'N/A')}")
    
    # Process IPN based on result code
    print(f"\n{'=' * 60}")
    print("Transaction Status")
    print(f"{'=' * 60}")
    result_code = sample_ipn_data['resultCode']
    
    if is_valid:
        if result_code == 0:
            print("✓ Transaction successful!")
            print(f"  Order ID: {sample_ipn_data['orderId']}")
            print(f"  Amount: {sample_ipn_data['amount']} VND")
            print(f"  Transaction ID: {sample_ipn_data['transId']}")
            print(f"  Message: {sample_ipn_data['message']}")
            # Here you would update your database, send confirmation, etc.
        elif result_code == 9000:
            print("✓ Transaction authorized successfully!")
        else:
            print("✗ Transaction failed!")
            print(f"  Result Code: {result_code}")
            print(f"  Message: {sample_ipn_data['message']}")
    else:
        print("✗ ERROR! Invalid signature - This transaction could be hacked!")
        print("  Please check your signature and returned signature")
    
    # Return response as required by Pay2S
    response = {
        "success": is_valid
    }
    
    print(f"\n{'=' * 60}")
    print("IPN Response (to send back to Pay2S)")
    print(f"{'=' * 60}")
    print(json.dumps(response, indent=2))
    
    # Assert that signature verification works
    assert is_valid, "IPN signature should be valid"
    assert result_code in [0, 9000], f"Result code should be 0 or 9000, got {result_code}"


if __name__ == "__main__":
    test_process_ipn()

