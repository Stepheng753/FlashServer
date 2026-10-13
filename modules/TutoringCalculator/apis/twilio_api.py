import datetime
import os
import re
import requests
from ..config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_API_KEY_SID,
    TWILIO_API_SECRET,
    TWILIO_FROM_NUMBER,
    TEXT_LOG_FILE,
    PST
)


def format_phone_e164(phone_str):
    """Normalizes phone numbers to E.164 format (+1XXXXXXXXXX)."""
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    elif len(digits) > 10 and not phone_str.startswith('+'):
        return f"+{digits}"
    elif phone_str.startswith('+'):
        return f"+{digits}"
    return phone_str


def log_text_message(student, phone, message, status, sid_or_error):
    timestamp = datetime.datetime.now(PST).strftime("%Y-%m-%d %I:%M:%S %p PST")
    log_entry = f"[{timestamp}] [{status.upper()}] To: {phone} (Student: {student}) | Details: {sid_or_error}\nMessage:\n{message}\n{'-'*60}\n"
    try:
        with open(TEXT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed writing to text log: {e}")


def send_sms(to_phone, message_body, student_name=""):
    """
    Sends an SMS using Twilio API Key & Secret via Twilio REST API.
    Logs each transaction to text_messages.log.
    """
    cleaned_phone = format_phone_e164(to_phone)
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

    data = {
        'From': TWILIO_FROM_NUMBER,
        'To': cleaned_phone,
        'Body': message_body
    }

    try:
        response = requests.post(
            url,
            data=data,
            auth=(TWILIO_API_KEY_SID, TWILIO_API_SECRET),
            timeout=10
        )
        res_json = response.json()

        if response.status_code in [200, 201]:
            msg_sid = res_json.get('sid', 'UNKNOWN_SID')
            log_text_message(student_name, cleaned_phone, message_body, "SENT", f"Twilio SID: {msg_sid}")
            return {"status": "sent", "phone": cleaned_phone, "student": student_name, "sid": msg_sid}
        else:
            err_msg = res_json.get('message', response.text)
            log_text_message(student_name, cleaned_phone, message_body, "FAILED", f"Error: {err_msg}")
            return {"status": "failed", "phone": cleaned_phone, "student": student_name, "error": err_msg}

    except Exception as e:
        log_text_message(student_name, cleaned_phone, message_body, "ERROR", str(e))
        return {"status": "error", "phone": cleaned_phone, "student": student_name, "error": str(e)}


def get_text_logs():
    """Reads and returns the complete text_messages.log file."""
    if not os.path.exists(TEXT_LOG_FILE):
        return "No text messages logged yet."
    try:
        with open(TEXT_LOG_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading log file: {e}"
