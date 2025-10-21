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
    Fetch phone info from OSINT API securely without exposing keys.
    Returns formatted string.
    """
    try:
        response = requests.post(OSINT_BASE_URL, data={'num': phone_number, 'key': OSINT_API_KEY})
        response.raise_for_status()
        data = response.json()  # assuming API returns JSON

        # Format JSON data into a readable string
        formatted = "\n".join([f"{k}: {v}" for k, v in data.items()])
        return formatted

    except requests.exceptions.RequestException as e:
        return f"Error fetching information: {str(e)}"
    except ValueError:
        return "Error: Invalid response from API"


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
    """Send message to Telegram chat securely."""
    try:
        requests.post(BASE_URL + 'sendMessage', json={'chat_id': chat_id, 'text': text})
    except Exception as e:
        print(f"Failed to send message: {e}")


# No app.run() needed if deploying to Vercel
