from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get environment variables
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
OSINT_API_KEY = os.getenv('OSINT_API_KEY')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Bot is running!"}), 200

def get_phone_info(phone_number):
    params = {
        'num': phone_number,
        'key': OSINT_API_KEY
    }
    try:
        response = requests.post(OSINT_BASE_URL, data=params)
        if response.status_code == 200:
            return response.text
        return "Error fetching information"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        if "text" in update["message"]:
            text = update["message"]["text"]
            
            # Check if input is a phone number
            if text.isdigit():
                # Get phone information
                result = get_phone_info(text)
                send_message(chat_id, f"Phone Number Information:\n{result}")
            else:
                send_message(chat_id, "Please send a valid phone number (digits only)")
    
    return 'Success', 200

def send_message(chat_id, text):
    url = BASE_URL + 'sendMessage'
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, json=payload)

app = Flask(__name__)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
