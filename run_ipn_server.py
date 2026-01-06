"""
Run IPN server for receiving Pay2S transaction confirmations.
"""
from src.pay2s.ipn import run_ipn_server
from config import SECRET_KEY, IPN_HOST, IPN_PORT

if __name__ == '__main__':
    # Run the IPN server
    # For production, use a proper WSGI server like gunicorn or uwsgi
    run_ipn_server(
        secret_key=SECRET_KEY,
        host=IPN_HOST,
        port=IPN_PORT,
        debug=True
    )