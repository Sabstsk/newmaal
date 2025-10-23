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

def edit_message_text(chat_id, message_id, text, parse_mode=None):
    """
    Edit a previously sent Telegram message.
    Returns True on success, False on failure.
    """
    try:
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'disable_web_page_preview': True
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode

        r = requests.post(BASE_URL + 'editMessageText', json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Error editing message: {e}")
        return False

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
        # Avoid printing sensitive info
        print(f"Requesting info for: {phone_number}")

        # Prepare base URL and params (don't concat query strings manually)
        base = OSINT_BASE_URL.rstrip('?')
        params = {"number": phone_number}
    

        # Use GET because POST returned "Method Not Allowed"
        response = requests.get(base, params=params, timeout=15)

        # Debug info
        print("Request URL:", response.url)
        print("Status code:", response.status_code)

        response.raise_for_status()

        # return JSON if possible, otherwise raw text
        try:
            return replace_mrx(beautify_json(response.json()))
        except ValueError:
            return "Something went wrong"

    except Exception as e:
        print(f"Error fetching data")
        return "Error fetching data"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" in update and "text" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"].strip()
        
        # --- Handle 10-digit number input ---
        if text.isdigit() and len(text) == 10:
            phone_number = text
            
            # 1. Send the initial "Searching" message and get its ID
            searching_text = f"/num {phone_number}\n\n🔎 Searching mobile database..."
            searching_message_id = send_message(chat_id, searching_text)
            
            # Check if sending failed
            if searching_message_id is None:
                return jsonify({"status": "error", "message": "Failed to send initial message"})
            
            # 2. Get the result
            result = get_phone_info(phone_number)
            
            # 3. Edit the original "Searching" message with the final result
            edit_message_text(chat_id, searching_message_id, result)
            
        else:
            # Send a friendly message if input is invalid
            send_message(chat_id, "⚠️ Lowde phone number!")

    return jsonify({"status": "success"})
    

def beautify_json(json_data):

    try:
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        # Beautify the JSON and return the indented version
        return json.dumps(json_data, indent=4)
    
    except (ValueError, TypeError) as e:
        # Handle invalid JSON input
        return f"Error beautifying JSON: {e}"
    
def replace_mrx(data):
    """
    Replace 'MRX' with 'Crazy' in JSON data or string.
    """
    s = json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
    return json.loads(s.replace('MRX', 'Crazy')) if isinstance(data, (dict, list)) else s.replace('MRX', 'Crazy')

if __name__ == '__main__':
    app.run(debug=True)






