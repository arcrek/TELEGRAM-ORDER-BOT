"""
Pay2S Signature Module
Functions for generating and verifying HMAC SHA256 signatures for Pay2S API requests and IPN notifications.
"""
import hmac
import hashlib


def generate_payment_signature(access_key, amount, ipn_url, order_id, order_info, partner_code, redirect_url, request_id, request_type, secret_key):
    """
    Generate HMAC SHA256 signature for Pay2S payment API request.
    
    Format: accessKey=$accessKey&amount=$amount&bankAccounts=Array&ipnUrl=$ipnUrl&orderId=$orderId&orderInfo=$orderInfo&partnerCode=$partnerCode&redirectUrl=$redirectUrl&requestId=$requestId&requestType=$requestType
    
    Args:
        access_key: Access key from Pay2S
        amount: Payment amount
        ipn_url: IPN callback URL
        order_id: Order ID
        order_info: Order information
        partner_code: Partner code
        redirect_url: Redirect URL after payment
        request_id: Request ID
        request_type: Request type (e.g., "pay2s")
        secret_key: Secret key for signature generation
    
    Returns:
        str: HMAC SHA256 signature
    """
    raw_hash = f"accessKey={access_key}&amount={amount}&bankAccounts=Array&ipnUrl={ipn_url}&orderId={order_id}&orderInfo={order_info}&partnerCode={partner_code}&redirectUrl={redirect_url}&requestId={request_id}&requestType={request_type}"
    signature = hmac.new(
        secret_key.encode('utf-8'),
        raw_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def generate_ipn_signature(access_key, amount, extra_data, message, order_id, order_info, order_type, partner_code, pay_type, request_id, response_time, result_code, trans_id, secret_key):
    """
    Generate HMAC SHA256 signature for IPN verification.
    
    Format: accessKey=$accessKey&amount=$amount&extraData=$extraData&message=$message&orderId=$orderId&orderInfo=$orderInfo&orderType=$orderType&partnerCode=$partnerCode&payType=$payType&requestId=$requestId&responseTime=$responseTime&resultCode=$resultCode&transId=$transId
    
    Args:
        access_key: Access key from Pay2S
        amount: Payment amount
        extra_data: Extra data (optional)
        message: Message from Pay2S
        order_id: Order ID
        order_info: Order information
        order_type: Order type
        partner_code: Partner code
        pay_type: Payment type
        request_id: Request ID
        response_time: Response time (milliseconds timestamp)
        result_code: Result code
        trans_id: Transaction ID
        secret_key: Secret key for signature generation
    
    Returns:
        str: HMAC SHA256 signature
    """
    raw_hash = f"accessKey={access_key}&amount={amount}&extraData={extra_data}&message={message}&orderId={order_id}&orderInfo={order_info}&orderType={order_type}&partnerCode={partner_code}&payType={pay_type}&requestId={request_id}&responseTime={response_time}&resultCode={result_code}&transId={trans_id}"
    signature = hmac.new(
        secret_key.encode('utf-8'),
        raw_hash.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_ipn_signature(ipn_data, secret_key):
    """
    Verify IPN signature from Pay2S.
    
    Args:
        ipn_data: Dictionary containing IPN data from Pay2S
        secret_key: Secret key for signature verification
    
    Returns:
        tuple: (is_valid: bool, partner_signature: str, debug_info: dict)
    """
    try:
        # Extract required fields
        access_key = ipn_data.get('accessKey', '')
        amount = ipn_data.get('amount', 0)
        extra_data = ipn_data.get('extraData', '')
        message = ipn_data.get('message', '')
        order_id = ipn_data.get('orderId', '')
        order_info = ipn_data.get('orderInfo', '')
        order_type = ipn_data.get('orderType', '')
        partner_code = ipn_data.get('partnerCode', '')
        pay_type = ipn_data.get('payType', '')
        request_id = ipn_data.get('requestId', '')
        response_time = ipn_data.get('responseTime', '')
        result_code = ipn_data.get('resultCode', '')
        trans_id = ipn_data.get('transId', '')
        # Pay2S may send signature as 'signature' or 'm2signature'
        received_signature = ipn_data.get('signature') or ipn_data.get('m2signature', '')
        
        # Generate signature
        # Convert all values to strings for consistent signature generation
        partner_signature = generate_ipn_signature(
            access_key=str(access_key),
            amount=str(amount),
            extra_data=str(extra_data),
            message=str(message),
            order_id=str(order_id),
            order_info=str(order_info),
            order_type=str(order_type),
            partner_code=str(partner_code),
            pay_type=str(pay_type),
            request_id=str(request_id),
            response_time=str(response_time),
            result_code=str(result_code),
            trans_id=str(trans_id),
            secret_key=secret_key
        )
        
        # Verify signature (timing-safe; received value is attacker-controlled)
        is_valid = hmac.compare_digest(str(received_signature), str(partner_signature))
        
        debug_info = {
            'rawHash': f"accessKey={access_key}&amount={amount}&extraData={extra_data}&message={message}&orderId={order_id}&orderInfo={order_info}&orderType={order_type}&partnerCode={partner_code}&payType={pay_type}&requestId={request_id}&responseTime={response_time}&resultCode={result_code}&transId={trans_id}",
            'pay2sSignature': received_signature,
            'partnerSignature': partner_signature
        }
        
        return is_valid, partner_signature, debug_info
        
    except Exception as e:
        return False, '', {'error': str(e)}

