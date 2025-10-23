from flask import Flask, request, jsonify
import requests
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running!"})

def send_message(chat_id, text):
    """Send message to Telegram chat and return message_id"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': True
        }
        response = requests.post(BASE_URL + 'sendMessage', json=payload)
        response.raise_for_status()
        return response.json()['result']['message_id']
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def get_phone_info(phone_number):
    try:
        print(f"Requesting info for: {phone_number}")
        base = OSINT_BASE_URL.rstrip('?')
        params = {"num": phone_number}  # Changed from "number" to "num"

        response = requests.get(base, params=params, timeout=15)
        print("Request URL:", response.url)
        print("Status code:", response.status_code)

        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"Error fetching data: {e}")
        return f"Error fetching data: {e}"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        
        if "message" in update and "text" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"].strip()
            
            if text.isdigit() and len(text) == 10:
                # Send initial message
                message_id = send_message(chat_id, f"🔍 Searching for: {text}...")
                
                # Get phone info
                result = get_phone_info(text)
                
                # Format and send result
                if isinstance(result, dict):
                    formatted_result = json.dumps(result, indent=2)
                else:
                    formatted_result = str(result)
                
                # Edit original message with results
                edit_message_text(chat_id, message_id, formatted_result)
            else:
                send_message(chat_id, "⚠️ Please send a valid 10-digit phone number!")
        
        return jsonify({"status": "success"})
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)






