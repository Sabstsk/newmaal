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
    try:
        response = requests.post(OSINT_BASE_URL+"?num="+phone_number+"&key="+OSINT_API_KEY)
        response.raise_for_status()
        return format_flipcart_info(response.json())
    except:
        return "Error fetching data"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update and "text" in update["message"]:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"]["text"]

        if text.isdigit():
            result = get_phone_info(text)
            send_message(chat_id, result)
        else:
            send_message(chat_id, "Are betichod sahi number bhej🤦‍♂️")

    return jsonify({"status": "success"})


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
