from twilio.rest import Client
import os

# Ensure environment variables are correctly loaded
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
WHATSAPP_FROM = "whatsapp:+14155238886"  # Replace with your Twilio sandbox number

def send_whatsapp_message(to: str, message: str) -> bool:
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            body=message,
            from_=WHATSAPP_FROM,
            to=to
        )
        return message.sid is not None
    except Exception as e:
        print("[whatsapp] Error:", e)
        return False

def send_whatsapp_image(to: str, image_url: str, caption: str = None) -> bool:
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        message = client.messages.create(
            media_url=[image_url],
            body=caption,
            from_=WHATSAPP_FROM,
            to=to
        )
        return message.sid is not None
    except Exception as e:
        print("[whatsapp] Error:", e)
        return False
