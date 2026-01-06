"""
WSGI entry point for Gunicorn production server.
"""
import os
from src.pay2s.ipn import create_ipn_app
from config import SECRET_KEY

# Create the Flask app
app = create_ipn_app(secret_key=SECRET_KEY)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('IPN_PORT', 5001)))

