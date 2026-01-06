"""
Pay2S Payment API Module
Functions for creating payment requests with Pay2S.
"""
import logging
import requests
from .signature import generate_payment_signature

logger = logging.getLogger(__name__)


def create_payment(
    endpoint,
    access_key,
    secret_key,
    partner_code,
    amount,
    order_id,
    order_info,
    redirect_url,
    ipn_url,
    bank_accounts,
    request_type="pay2s",
    partner_name=None,
    request_id=None
):
    """
    Create a payment request with Pay2S.
    
    Args:
        endpoint: Pay2S API endpoint URL
        access_key: Access key from Pay2S
        secret_key: Secret key for signature generation
        partner_code: Partner code
        amount: Payment amount (VND)
        order_id: Order ID
        order_info: Order information (10-32 characters, alphanumeric only)
        redirect_url: URL to redirect after payment
        ipn_url: IPN callback URL
        bank_accounts: List of bank accounts [{"account_number": "...", "bank_id": "..."}]
        request_type: Request type (default: "pay2s")
        partner_name: Partner name (optional)
        request_id: Request ID (defaults to order_id if not provided)
    
    Returns:
        dict: Response from Pay2S API containing payUrl if successful
    """
    if request_id is None:
        request_id = str(order_id)
    
    if partner_name is None:
        partner_name = "Pay2S Payment"
    
    # Generate signature
    signature = generate_payment_signature(
        access_key=access_key,
        amount=amount,
        ipn_url=ipn_url,
        order_id=str(order_id),
        order_info=order_info,
        partner_code=partner_code,
        redirect_url=redirect_url,
        request_id=str(request_id),
        request_type=request_type,
        secret_key=secret_key
    )
    
    # Prepare request data
    data = {
        "accessKey": access_key,
        "partnerCode": partner_code,
        "partnerName": partner_name,
        "requestId": str(request_id),
        "amount": amount,
        "orderId": str(order_id),
        "orderInfo": order_info,
        "orderType": request_type,
        "bankAccounts": bank_accounts,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "requestType": request_type,
        "signature": signature
    }
    
    # Set headers
    headers = {
        "Content-Type": "application/json; charset=UTF-8"
    }
    
    # Validate endpoint before making request
    if not endpoint or endpoint == '...' or not endpoint.startswith(('http://', 'https://')):
        raise ValueError(
            f"Invalid payment endpoint: {repr(endpoint)}. "
            "Please set PAY2S_ENDPOINT environment variable or update config/config.py"
        )
    
    # Log request data (mask sensitive info)
    log_data = data.copy()
    log_data["accessKey"] = log_data["accessKey"][:8] + "..." if len(log_data["accessKey"]) > 8 else "***"
    log_data["signature"] = log_data["signature"][:16] + "..." if len(log_data["signature"]) > 16 else "***"
    logger.info(f"Pay2S Request: POST {endpoint}")
    logger.info(f"Pay2S bankAccounts: {data['bankAccounts']}")
    logger.debug(f"Pay2S Request Data: {log_data}")
    
    # Log the exact JSON that will be sent
    import json as json_module
    logger.debug(f"Pay2S Request JSON: {json_module.dumps(data, ensure_ascii=False)}")
    
    # Make POST request
    try:
        response = requests.post(
            endpoint,
            json=data,
            headers=headers,
            timeout=10
        )
        
        # Log response
        logger.info(f"Pay2S Response Status: {response.status_code}")
        try:
            response_json = response.json()
            logger.info(f"Pay2S Response resultCode: {response_json.get('resultCode')}, message: {response_json.get('message')}")
            logger.debug(f"Pay2S Response: {response_json}")
        except:
            logger.warning(f"Pay2S Response (non-JSON): {response.text[:500]}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as e:
        raise Exception(
            f"Connection error to payment gateway: {endpoint}\n"
            f"Details: {str(e)}\n"
            f"Please check if the payment gateway is reachable and properly configured."
        )
    except requests.exceptions.Timeout as e:
        raise Exception(
            f"Payment gateway request timeout.\n"
            f"Endpoint: {endpoint}\n"
            f"Details: {str(e)}"
        )
    except requests.exceptions.HTTPError as e:
        raise Exception(
            f"HTTP error from payment gateway: {str(e)}\n"
            f"Status code: {e.response.status_code}\n"
            f"Response: {e.response.text if hasattr(e.response, 'text') else 'N/A'}"
        )
    except ValueError as e:
        # JSON decode error
        raise Exception(
            f"Invalid response from payment gateway.\n"
            f"Failed to parse JSON: {str(e)}"
        )
    except requests.exceptions.RequestException as e:
        raise Exception(
            f"Payment request error: {str(e)}\n"
            f"Please check your payment configuration and try again."
        )

