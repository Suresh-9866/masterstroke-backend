import os
import httpx
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def send_whatsapp_template(to_phone: str, template_name: str = "hello_world", language_code: str = "en_US") -> bool:
    """
    Sends a WhatsApp message via Meta Cloud API using an approved template.
    Fast, synchronous/threaded worker compatible with FastAPI BackgroundTasks.
    """
    phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID", "")
    access_token = os.getenv("META_WA_ACCESS_TOKEN", "")

    if not phone_number_id or not access_token:
        print("[WhatsApp] Meta WhatsApp credentials not configured in environment (.env). Skipping WhatsApp dispatch.")
        return False


    if not to_phone:
        return False

    # Clean phone number (Ensure country code without '+' or spaces)
    clean_phone = "".join(filter(str.isdigit, to_phone))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone  # Default to India (+91) if 10 digits

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code}
        }
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            print(f"WhatsApp Meta API Response [{response.status_code}]: {response.text}")
            return response.status_code == 200
    except Exception as e:
        print(f"Error sending Meta WhatsApp message to {clean_phone}: {e}")
        return False
