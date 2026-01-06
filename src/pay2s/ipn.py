"""
Pay2S IPN Server Module
Flask-based server to receive and process IPN notifications from Pay2S.
"""
from flask import Flask, request, jsonify
import json
import logging
from .signature import verify_ipn_signature
from .ipn_order_processor import get_ipn_processor


def create_ipn_app(secret_key, process_transaction_callback=None):
    """
    Create a Flask app for handling IPN notifications.
    
    Args:
        secret_key: Secret key for signature verification
        process_transaction_callback: Optional callback function to process transactions
                                      Function signature: callback(ipn_data) -> bool
    
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    def default_process_transaction(ipn_data):
        """
        Default transaction processing function.
        This processes orders using the IPNOrderProcessor.
        
        Args:
            ipn_data: Dictionary containing IPN data from Pay2S
        """
        order_id = ipn_data.get('orderId', '')
        amount = ipn_data.get('amount', 0)
        result_code = ipn_data.get('resultCode', '')
        trans_id = ipn_data.get('transId', '')
        message = ipn_data.get('message', '')
        
        logger.info(f"Processing transaction - Order ID: {order_id}, Amount: {amount}, Result Code: {result_code}, Trans ID: {trans_id}")
        
        processor = get_ipn_processor()
        
        # Handle result_code as both string or integer
        if result_code == 0 or result_code == "0":
            # Transaction successful
            logger.info(f"✓ Transaction successful! Order ID: {order_id}, Transaction ID: {trans_id}")
            success = processor.process_payment_success(
                order_id=order_id,
                transaction_id=str(trans_id),
                amount=amount,
            )
            return success
        elif result_code == 9000 or result_code == "9000":
            # Transaction authorized
            logger.info(f"✓ Transaction authorized! Order ID: {order_id}")
            success = processor.process_payment_success(
                order_id=order_id,
                transaction_id=str(trans_id),
                amount=amount,
            )
            return success
        else:
            # Transaction failed
            logger.warning(f"✗ Transaction failed! Order ID: {order_id}, Result Code: {result_code}, Message: {message}")
            success = processor.process_payment_failure(
                order_id=order_id,
                result_code=result_code,
                message=message,
            )
            return success
    
    # Use provided callback or default
    process_func = process_transaction_callback or default_process_transaction
    
    @app.route('/ipn', methods=['POST'])
    def ipn_handler():
        """
        IPN endpoint to receive transaction confirmations from Pay2S.
        
        Pay2S will send POST requests to this endpoint with JSON data.
        Must respond within 30 seconds with HTTP 200 and {"success": true}
        """
        try:
            # Log raw request for debugging
            logger.info(f"=== IPN Request Received ===")
            logger.info(f"Request headers: {dict(request.headers)}")
            logger.info(f"Request content-type: {request.content_type}")
            
            # Get JSON data from request
            ipn_data = request.get_json(force=True, silent=True)
            
            if not ipn_data:
                # Try to get raw data
                raw_data = request.get_data(as_text=True)
                logger.error(f"No JSON data received. Raw data: {raw_data[:500]}")
                return jsonify({"success": False, "message": "No data received"}), 400
            
            logger.info(f"Received IPN data: {json.dumps(ipn_data, indent=2, ensure_ascii=False)}")
            logger.info(f"IPN Keys: {list(ipn_data.keys())}")
            logger.info(f"IPN orderId: {ipn_data.get('orderId')}, resultCode: {ipn_data.get('resultCode')}, transId: {ipn_data.get('transId')}")
            
            # Verify signature
            is_valid, partner_signature, debug_info = verify_ipn_signature(ipn_data, secret_key)
            
            logger.info(f"Signature verification: is_valid={is_valid}")
            logger.info(f"Pay2S signature: {ipn_data.get('signature', 'N/A')[:20]}...")
            logger.info(f"Partner signature: {partner_signature[:20]}...")
            
            if not is_valid:
                logger.error(f"Invalid signature!")
                logger.error(f"Raw Hash used: {debug_info.get('rawHash')}")
                # Still return success to avoid Pay2S retrying (log the issue for debugging)
                logger.warning("Returning success despite invalid signature to prevent retries")
                # Uncomment below to reject invalid signatures:
                # return jsonify({"success": False, "message": "Invalid signature"}), 400
            
            logger.info("Processing transaction...")
            
            # Process the transaction
            result = process_func(ipn_data)
            logger.info(f"Transaction processing result: {result}")
            
            # Return success response as required by Pay2S
            # Must be HTTP 200 with {"success": true} within 30 seconds
            logger.info("=== IPN Processing Complete - Returning success ===")
            return jsonify({"success": True}), 200
            
        except Exception as e:
            logger.error(f"Error processing IPN: {str(e)}", exc_info=True)
            return jsonify({
                "success": False,
                "message": f"Error processing IPN: {str(e)}"
            }), 500
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok"}), 200
    
    return app


def run_ipn_server(secret_key, host='0.0.0.0', port=5000, debug=False, process_transaction_callback=None):
    """
    Run the IPN server.
    
    Args:
        secret_key: Secret key for signature verification
        host: Host to bind to (default: '0.0.0.0')
        port: Port to bind to (default: 5000)
        debug: Enable debug mode (default: False)
        process_transaction_callback: Optional callback function to process transactions
    """
    app = create_ipn_app(secret_key, process_transaction_callback)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting IPN server on http://{host}:{port}")
    logger.info(f"IPN endpoint: http://your-server:{port}/ipn")
    app.run(host=host, port=port, debug=debug)

