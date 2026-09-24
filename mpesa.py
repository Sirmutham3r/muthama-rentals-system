import os
import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime

# --- Credentials (now pulled from environment variables) ---
# Set these in your .env file locally AND in Vercel > Project > Settings > Environment Variables.
# The shortcode/passkey below are Safaricom's public sandbox test values, so they're safe to
# keep as fallbacks -- but CONSUMER_KEY and CONSUMER_SECRET are specific to your Daraja app
# and should never be hardcoded or committed to a public repo.
CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')

BUSINESS_SHORT_CODE = os.getenv('MPESA_SHORTCODE', '174379')
PASSKEY = os.getenv('MPESA_PASSKEY', 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://muthama-rentals-system.vercel.app/mpesa/callback')


def get_access_token():
    """Authenticates with Safaricom and returns a temporary access token."""
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        response = requests.get(api_url, auth=HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET), timeout=15)
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        print(f"Failed to get access token. Error: {e}")
        return None


def _build_password_and_timestamp():
    """Shared helper: generates the Base64 password and timestamp Safaricom expects."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = BUSINESS_SHORT_CODE + PASSKEY + timestamp
    encoded_password = base64.b64encode(password_str.encode('ascii')).decode('utf-8')
    return encoded_password, timestamp


def trigger_stk_push(phone_number, amount, account_reference):
    """
    Triggers an M-Pesa STK Push to the specified phone number.
    phone_number format: '2547XXXXXXXX'
    Returns the raw Safaricom response, which includes 'CheckoutRequestID' on success --
    store that ID so you can poll query_stk_status() if the callback webhook doesn't arrive.
    """
    access_token = get_access_token()
    if not access_token:
        return {"error": "Could not generate access token."}

    encoded_password, timestamp = _build_password_and_timestamp()

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
        "Amount": int(amount),  # Safaricom expects an integer
        "PartyA": phone_number,
        "PartyB": BUSINESS_SHORT_CODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": "Rent Payment"
    }

    print(f"[trigger_stk_push] Sending STK push to {phone_number} for KES {amount}. CallBackURL={CALLBACK_URL}")

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        result = response.json()
        print(f"[trigger_stk_push] Safaricom response: {result}")
        return result
    except Exception as e:
        print(f"STK Push failed. Error: {e}")
        return {"error": str(e)}


def query_stk_status(checkout_request_id):
    """
    Actively queries Safaricom for the result of an STK push.
    Use this as a FALLBACK when the callback webhook (/mpesa/callback) hasn't arrived
    within a reasonable time -- sandbox callback delivery is known to be unreliable.

    ResultCode '0' in the response means the transaction was completed successfully.
    Any other ResultCode (or the absence of one, while Safaricom is still processing)
    means it either failed, was cancelled, or is still pending.
    """
    access_token = get_access_token()
    if not access_token:
        return {"error": "Could not generate access token."}

    encoded_password, timestamp = _build_password_and_timestamp()

    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "BusinessShortCode": BUSINESS_SHORT_CODE,
        "Password": encoded_password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        result = response.json()
        print(f"[query_stk_status] Query result for {checkout_request_id}: {result}")
        return result
    except Exception as e:
        print(f"STK status query failed. Error: {e}")
        return {"error": str(e)}


# --- TESTING BLOCK (only runs when you execute this file directly, e.g. `python mpesa.py`) ---
if __name__ == '__main__':
    print("Testing M-Pesa STK Push...")

    test_phone = "254117382361"
    test_amount = 1
    test_door = "Door SR-01"

    print(f"Sending prompt for KES {test_amount} to {test_phone}...")
    result = trigger_stk_push(test_phone, test_amount, test_door)
    print("Safaricom Response:")
    print(result)

    checkout_id = result.get('CheckoutRequestID')
    if checkout_id:
        input("Enter your PIN on your phone, then press Enter here to query status...")
        status = query_stk_status(checkout_id)
        print("Query Response:")
        print(status)