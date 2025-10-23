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


# ...existing code...
def get_phone_info(phone_number):
    try:
        # Avoid printing sensitive info
        print(f"Requesting info for: {phone_number}")

        # Prepare base URL and params (don't concat query strings manually)
        base = OSINT_BASE_URL.rstrip('?')
        params = {"number": phone_number}
        api_key = os.getenv("OSINT_API_KEY")
        if api_key:
            params["key"] = api_key

        # Use GET because POST returned "Method Not Allowed"
        response = requests.get(base, params=params, timeout=3)

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
            send_message(chat_id, "⚠️ Please send a valid 10-digit phone number!")

    return jsonify({"status": "success"})

def send_message(chat_id, text):
    """
    Sends a message via Telegram API and returns the message_id.
    """
    # NOTE: This requires your actual 'bot' object to be accessible
    try:
        # The API call returns a Message object, we need its ID
        sent_message = bot.send_message(chat_id, text)
        return sent_message.message_id
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def format_flipcart_info(data):
    formatted_results = ["ℹ️ Flipcart Information\n"]
    
    for idx, entry in enumerate(data):
        result = []
        
        # Start formatting each result
        result.append(f"✨ Result {idx + 1} ✨")
        result.append(f"➡️ Id: {entry.get('id', 'N/A')}")
        result.append(f"📱 Mobile: {entry.get('mobile', 'N/A')}")
        result.append(f"👤 Name: {entry.get('name', 'N/A')}")
        result.append(f"➡️ Father_name: {entry.get('father_name', 'N/A')}")
        
        # Handle address with formatting
        address = entry.get("address", "N/A")
        address = address.replace("!!", ", ").replace("!", ", ")
        result.append(f"🏠 Address: {address}")
        
        # Handle circle
        result.append(f"📡 Circle: {entry.get('circle', 'N/A')}")
        
        # Add Aadhaar No. if available
        if entry.get("id_number"):
            result.append(f"🆔 Aadhaar No.: {entry['id_number']}")
        
        # Add alt_mobile if available
        if entry.get("alt_mobile"):
            result.append(f"📱 Alt_mobile: {entry['alt_mobile']}")
        
        # Join the formatted result for this entry and add it to the overall results
        formatted_results.append("\n".join(result))
        formatted_results.append("\n" + "="*50 + "\n")
    
    # Join all formatted results with a newline between them
    return "\n".join(formatted_results)

def beautify_json(json_data):

    try:
        # If json_data is a string, try to parse it into a Python object (dict/list)
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        # Beautify the JSON and return the indented version
        return json.dumps(json_data, indent=4)
    
    except (ValueError, TypeError) as e:
        # Handle invalid JSON input
        return f"Error beautifying JSON: {e}"

def send_message(chat_id, text):
    """Send raw message to Telegram chat"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'disable_web_page_preview': True
    }
    requests.post(BASE_URL + 'sendMessage', json=payload)


def replace_mrx(data):
    # Convert dict/list to JSON string if needed
    s = json.dumps(data) if isinstance(data, (dict, list)) else data
    # Replace and return as the same type
    return json.loads(s.replace('MRX', 'Crazy')) if isinstance(data, (dict, list)) else s.replace('MRX', 'Crazy')


