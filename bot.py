from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
OSINT_API_KEY = os.getenv('OSINT_API_KEY')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running!"})


def get_phone_info(phone_number):
    """
    Fetch phone info from OSINT API and format it securely for Telegram
    """
    try:
        response = requests.post(OSINT_BASE_URL, data={'num': phone_number, 'key': OSINT_API_KEY})
        response.raise_for_status()
        
        # Parse and format the response data securely
        data = response.text.strip()
        
        # Create a clean, formatted message
        formatted_result = (
            f"📱 *Phone Number Analysis*\n\n"
            f"Number: `{phone_number}`\n"
            f"───────────────\n"
            f"{data}\n"
            f"───────────────\n"
            f"_Powered by OSINT_"
        )
        
        return formatted_result

    except requests.exceptions.RequestException as e:
        return "❌ Unable to fetch information at this time"
    except Exception as e:
        return "❌ An unexpected error occurred"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"]

        if text.isdigit():
            result = get_phone_info(text)
            send_message(chat_id, f"📱 Phone Number Info:\n{result}")
        else:
            send_message(chat_id, "❌ Please send a valid phone number (digits only)")

    return jsonify({"status": "success"})


def send_message(chat_id, text):
    """Send formatted message to Telegram chat"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        requests.post(BASE_URL + 'sendMessage', json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")


# No app.run() needed if deploying to Vercel
