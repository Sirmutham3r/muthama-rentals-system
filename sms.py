import os
import africastalking

# In Africa's Talking sandbox mode, AT_USERNAME must literally be "sandbox"
# and AT_API_KEY is the sandbox key from your AT dashboard. For production,
# AT_USERNAME is your real app username and AT_API_KEY is the live key.
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY")

_initialized = False


def _init():
    global _initialized
    if not _initialized:
        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        _initialized = True


def send_sms(phone_number, message):
    """
    phone_number is expected in '2547XXXXXXXX' format (how it's stored on
    Tenant) -- Africa's Talking wants the leading '+'.

    Returns True if AT accepted the message for delivery, False otherwise.
    Never raises: a flaky SMS gateway should not crash the login flow, it
    should just fail the OTP send and let the caller flash an error.
    """
    to = phone_number if phone_number.startswith('+') else f"+{phone_number}"

    try:
        _init()
        sms = africastalking.SMS
        response = sms.send(message, [to])
        print(f"AT SMS response: {response}")

        recipients = response.get('SMSMessageData', {}).get('Recipients', [])
        # statusCode 101 == "Sent" in Africa's Talking's API
        if recipients and recipients[0].get('statusCode') == 101:
            return True

        print(f"AT SMS not accepted: {recipients}")
        return False
    except Exception as e:
        print(f"AT SMS error: {e}")
        return False