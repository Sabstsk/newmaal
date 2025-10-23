from flask import Flask, request, jsonify
import requests
import json
import os
import telegram  # New import for Bot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

# --- Initialize Telegram Bot (NEW) ---
bot = telegram.Bot(token=API_TOKEN)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Server is running!"})

def get_phone_info(phone_number):
    try:
        # Debug log
        print(f"🔍 Requesting info for: {phone_number}")

        # Prepare base URL and params
        base = OSINT_BASE_URL.rstrip('?')
        params = {"number": phone_number}
        
        # Timeout reduced to 5 seconds (avoid Telegram timeout)
        response = requests.get(base, params=params, timeout=5)

        # Debug info
        print(f"🌐 Request URL: {response.url}")
        print(f"📡 Status code: {response.status_code}")

        # Raise error for bad status        response.raise_for_status()

        # Return JSON if possible, otherwise raw text
        try:
            return replace_mrx(beautify_json(response.json()))
        except json.JSONDecodeError:
            return "❌ Invalid data from API"

    except requests.exceptions.Timeout:
        print("⏰ Timeout error")
        return "❌ Request timed out"
    except requests.exceptions.HTTPError as e:
        print(f"📛 HTTP Error: {e}")
        return f"❌ API Error: {response.status_code}"
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return "❌ Error fetching data"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    
    # --- Immediate valid response (avoid Telegram timeout) ---
    if not update or "message" not in update:
        print(f"📥 Ignoring non-message update: {update}")
        return jsonify({"status": "ignored"}), 200  # Must be 200

    chat_id = update["message"]["chat"]["id"]
    text = update["message"]["text"].strip()
    print(f"💬 Received from {chat_id}: {text}")  # Debug log
    
    # --- Handle command-style input (e.g., /1234567890) ---
    cleaned_text = text.lstrip('/')  # Remove leading '/'
    
    # --- Handle 10-digit number input ---
    if cleaned_text.isdigit() and len(cleaned_text) == 10:
        phone_number = cleaned_text
        
        # 1. Send initial "Searching" message
        searching_text = f"/num {phone_number}\n\n🔎 Searching mobile database..."
        try:
            sent_message = bot.send_message(chat_id, searching_text)
            searching_message_id = sent_message.message_id
            print(f"📤 Sent searching msg ID: {searching_message_id}")
        except Exception as e:
            print(f"❌ Failed to send message: {e}")
            return jsonify({"status": "success"}), 200  # Still OK
        
        # 2. Get result (API call)
        result = get_phone_info(phone_number)
        if "❌" not in str(result) and not isinstance(result, str):
            result = json.dumps(result, indent=2)  # Convert dict to str if needed
        
        # 3. Edit the original message
        try:
            success = edit_message_text(chat_id, searching_message_id, str(result))
            if not success:
                print("❌ Failed to edit message")
        except Exception as e:
            print(f"❌ Edit failed: {e}")
    
    else:
        # 4. Invalid input
        try:
            bot.send_message(chat_id, "⚠️ Lowde phone number! Send 10-digit number.")
        except Exception as e:
            print(f"❌ Failed to send error message: {e}")

    return jsonify({"status": "success"}), 200  # Final OK

def edit_message_text(chat_id, message_id, text, parse_mode=None):
    """
    Edit a previously sent Telegram message.
    Returns True on success, False on failure.
    """
    try:
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': str(text)[:4000],  # Truncate long messages
            'disable_web_page_preview': True
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode

        r = requests.post(BASE_URL + 'editMessageText', json=payload, timeout=5)
        r.raise_for_status()
        print(f"✏️ Edited message {message_id} successfully")
        return True
    except Exception as e:
        print(f"💥 Edit failed: {e}")
        return False

# --- Helper functions (no changes) ---
def beautify_json(json_data):
    try:
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        return json.dumps(json_data, indent=4)
    except (ValueError, TypeError) as e:
        return f"Error beautifying JSON: {e}"

def replace_mrx(data):
    s = json.dumps(data) if isinstance(data, (dict, list)) else data
    return json.loads(s.replace('MRX', 'Crazy')) if isinstance(data, (dict, list)) else s.replace('MRX', 'Crazy')

# --- Health check ---
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)  # Debug=False for prod