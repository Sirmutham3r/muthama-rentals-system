import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime

# Your Safaricom Daraja Sandbox Credentials
CONSUMER_KEY = '4SUDfbw1RGQ1UzcOgfw8RdPWEE27Cjr6uIa7oQdwbYgLGPr0'
CONSUMER_SECRET = 'mU8ydCYeH2q8loUTGYfAZ53Rch8f83qpFuZOPevJSwXzO5UlN8WZdbbZNAEsi6ng'

# Safaricom Sandbox Test Credentials
BUSINESS_SHORT_CODE = "174379"
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"

def get_access_token():
    """Authenticates with Safaricom and returns a temporary access token."""
    api_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        response = requests.get(api_URL, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET))
        return response.json()['access_token']
    except Exception as e:
        print(f"Failed to get token. Error: {e}")
        return None

def trigger_stk_push(phone_number, amount, account_reference):
    """
    Triggers an M-Pesa STK Push to the specified phone number.
    phone_number format: '2547XXXXXXXX'
    """
    access_token = get_access_token()
    if not access_token:
        return {"error": "Could not generate access token."}
        
    # 1. Generate Timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # 2. Generate Password (Base64 encode: Shortcode + Passkey + Timestamp)
    password_str = BUSINESS_SHORT_CODE + PASSKEY + timestamp
    password_bytes = password_str.encode('ascii')
    encoded_password = base64.b64encode(password_bytes).decode('utf-8')
    
    # 3. Setup Request Headers and Payload
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "BusinessShortCode": BUSINESS_SHORT_CODE,
        "Password": encoded_password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount), # Safaricom expects an integer
        "PartyA": phone_number,
        "PartyB": BUSINESS_SHORT_CODE,
        "PhoneNumber": phone_number,
        # IMPORTANT: Replace YOUR_NGROK_URL with your actual Ngrok HTTPS link 
        "CallBackURL": "https://muthama-rentals-system.vercel.app/mpesa/callback",
        "AccountReference": account_reference,
        "TransactionDesc": "Rent Payment"
    }
    
    # 4. Send Request to Safaricom
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        print(f"STK Push Failed. Error: {e}")
        return {"error": str(e)}

# --- TESTING BLOCK (Placed safely at the bottom) ---
if __name__ == '__main__':
    print("Testing M-Pesa STK Push...")
    
    test_phone = "254117382361" 
    test_amount = 1 
    test_door = "Door SR-01"
    
    print(f"Sending prompt for KES {test_amount} to {test_phone}...")
    result = trigger_stk_push(test_phone, test_amount, test_door)
    print("Safaricom Response:")
    print(result)