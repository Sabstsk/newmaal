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
    Fetch phone info from OSINT API and return JSON
    """
    try:
        response = requests.post(OSINT_BASE_URL, data={'num': phone_number, 'key': OSINT_API_KEY})
        response.raise_for_status()
        data = response.raw # parse JSON response
        return data
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except ValueError:
        return {"error": "Invalid response from OSINT API"}


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"]

        if text.isdigit():
            result = get_phone_info(text)
            # Send formatted JSON as message
            send_message(chat_id, jsonify(result).get_data(as_text=True))
        else:
            send_message(chat_id, "❌ Please send a valid phone number (digits only)")

    return jsonify({"status": "success"})


def send_message(chat_id, text):
    """Send message to Telegram chat"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': True
    }
    requests.post(BASE_URL + 'sendMessage', json=payload)
