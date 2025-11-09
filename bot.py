from flask import Flask, request, jsonify
import requests
import os
import json
import html
from dotenv import load_dotenv
import asyncio
import re
import random
from io import BytesIO            # <-- added

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
API_KEY=os.getenv('API_KEY')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Bot is running!"})

def edit_message_text(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    """
    Edit a previously sent Telegram message.
    Returns True on success, False on failure.
    Accepts optional reply_markup (dict) to add inline buttons.
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
        if reply_markup:
            payload['reply_markup'] = reply_markup

        r = requests.post(BASE_URL + 'editMessageText', json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Error editing message: {e}")
        return False

def send_message(chat_id, text, parse_mode=None, reply_to_message_id=None, reply_markup=None):
    """Send message to Telegram chat and return message_id"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': True
        }
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id
        if reply_markup:
            payload['reply_markup'] = reply_markup

        response = requests.post(BASE_URL + 'sendMessage', json=payload, timeout=10)
        response.raise_for_status()
        return response.json()['result']['message_id']
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def get_phone_info(phone_number):

    try:
        print(f"Requesting info for: {phone_number}")
        base = (OSINT_BASE_URL or "").rstrip('?')
        if not base:
            print("OSINT_BASE_URL not configured")
            return {"error": "Service not configured"}

        params = {}
        if API_KEY:
            params['key'] = API_KEY
        params['number'] = str(phone_number)

        # Try GET first (builds URL like base?key=...&number=...)
        resp = requests.get(base, params=params, timeout=15)
        print("Request URL:", getattr(resp, "url", base))
        print("Status code:", resp.status_code)

        # If GET not allowed, retry with POST
        if resp.status_code == 405:
            print("GET returned 405, retrying with POST")
            resp = requests.post(base, data=params, timeout=15)
            print("POST attempted, status:", resp.status_code)

        # show truncated response for debugging
        text_preview = resp.text[:1000] + ("..." if len(resp.text) > 1000 else "")
        print("Response (preview):", text_preview)

        try:
            resp.raise_for_status()
        except requests.HTTPError:
            # return body so caller can show it
            return resp.text or f"HTTP {resp.status_code}"

        # Prefer JSON; otherwise return raw text
        try:
            return resp.json()
        except ValueError:
            return resp.text or "No content"

    except requests.Timeout:
        # Hide sensitive information for timeout errors
        print(f"Timeout error for number: {phone_number}")
        return {"error": "timeout"}
    except requests.ConnectionError:
        # Hide connection details
        print(f"Connection error for number: {phone_number}")
        return {"error": "connection"}
    except Exception as e:
        # Log full error on server but return generic message
        print(f"Error fetching data: {type(e).__name__} - {e}")
        return {"error": "service_unavailable"}

def choose_no_data_message():
    """
    Return a creative/abusive message when no data is found.
    """
    messages = [
        "🤬 Bhai kuch bhi nahi mila! Kya bakchodi number hai ye? Database mein nahi hai.",
        "😤 Oye lowde, yeh number toh ghost hai! Kuch data nahi hai mere paas.",
        "🚫 Are yaar, khaali haath reh gaye. Iss number ka kuch nahi mila.",
        "😒 Kya faltu number diya hai? Database mein ghanta kuch nahi hai.",
        "🤦‍♂️ Abe yeh number toh bekaar hai! Koi info nahi hai bhai.",
        "💀 RIP bro, iss number ka data toh gaya bhaad mein. Kuch nahi mila.",
        "😑 Gandmasti mat kar, yeh number fake lagta hai. Data nahi mila."
    ]
    return random.choice(messages)

def choose_abusive_message(text):
    """
    Return a short abusive message variant depending on the user's wrong input.
    """
    # Variants for different mistakes
    plus_msgs = [
        "⚠️ Plus mat lagao yaar — seedha 10-digit number bhejo. Bakchodi band karo 😒",
        "🤦‍♂️ +91 hatao aur sirf 10 digits bhejo. Gandmasti chhod."
    ]
    space_msgs = [
        "⚠️ Space mat daalo — number continuous 10 digits chahiye. Lowde, sudhar jao.",
        "🤨 Beech mein space mat daalo, number sahi bhejo."
    ]
    nondigit_msgs = [
        "❌ Alphabets/special chars nahi chalega — sirf digits bhejo. Bakchodi mat kar.",
        "😑 Phone mein letters nahi chalte. Seedha 10-digit number bhejo."
    ]
    length_msgs = [
        "⚠️ Number ka size galat hai — 10 digits chahiye. Gandmasti toh dekho.",
        "🚫 10-digit number bhejo, warna bakchodi band karo."
    ]
    default_msgs = [
        "⚠️ Galat format — sirf 10-digit number bhejo. Samjha?",
        "😒 Number sahi nahi hai. Seedha 10-digit number bhejo."
    ]

    if text.startswith('+'):
        return random.choice(plus_msgs)
    if ' ' in text:
        return random.choice(space_msgs)
    if not re.search(r'^\d+$', text):
        return random.choice(nondigit_msgs)
    if len(re.sub(r'\D', '', text)) != 10:
        return random.choice(length_msgs)
    return random.choice(default_msgs)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json() or {}
    
    # Handle callback query (inline button clicks)
    if "callback_query" in update:
        return handle_callback_query(update["callback_query"])
    
    message = update.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type", "")
    user = message.get("from") or {}
    user_message_id = message.get("message_id")

    if not chat_id:
        return jsonify({"status": "ignored", "reason": "no chat id"})

    # /start handler (unchanged)
    if text.startswith("/start") or text.startswith("/help"):
        welcome = (
            "Welcome — Phone Lookup Bot!\n\n"
            "Send a 10-digit phone number and I'll return the raw JSON result.\n\n"
            "Examples:\n"
            "- 9876543210\n\n"
            "Note: The bot returns raw JSON; use the \"Copy JSON\" button to copy the data."
        )
        send_message(chat_id, welcome)
        return jsonify({"status": "ok", "action": "sent_welcome"})

    # Validate input and send tailored abusive message when format is wrong
    if not re.fullmatch(r'\d{10}', text):
        abuse = choose_abusive_message(text)
        send_message(chat_id, abuse)
        return jsonify({"status": "ok", "action": "invalid_format"})

    # At this point text is exactly 10 digits
    phone_number = text

    # 1. Send the initial "Searching" message and get its ID
    searching_text = f"/num {phone_number}\n\n🔎 Searching mobile database..."
    searching_message_id = send_message(chat_id, searching_text)

    if searching_message_id is None:
        return jsonify({"status": "error", "message": "Failed to send initial message"})

    # 2. Get the result
    result = get_phone_info(phone_number)
    
    # Handle error responses
    if isinstance(result, dict) and 'error' in result:
        # Delete the searching message
        try:
            requests.post(BASE_URL + 'deleteMessage', json={
                'chat_id': chat_id,
                'message_id': searching_message_id
            }, timeout=10)
        except Exception as e:
            print(f"Error deleting searching message: {e}")
        
        # Map error types to user-friendly messages
        error_messages = {
            "timeout": "⏱️ Saiyaara, server response nahi de raha! Thoda time out ho gaya.\n\n😤 Phir se try kar bhai, server slow chal raha hai.",
            "connection": "🔌 Abe yaar, connection issue hai! Server tak pohoch nahi paa rahe.\n\n🤦‍♂️ Thodi der baad dobara try kar.",
            "service_unavailable": "🚫 Service abhi available nahi hai bhai!\n\n😑 Thoda wait kar aur phir try kar."
        }
        
        error_type = result.get('error', 'service_unavailable')
        error_msg = error_messages.get(error_type, error_messages['service_unavailable'])
        
        send_message(chat_id, error_msg)
        return jsonify({"status": "error", "action": "service_error", "error_type": error_type})

    # Format the result using format_flipcart_info
    try:
        if isinstance(result, (dict, list)):
            # Extract data array if wrapped in 'data' key
            if isinstance(result, dict) and 'data' in result:
                data = result['data']
            else:
                data = result if isinstance(result, list) else [result]
            formatted_text = format_flipcart_info(data)
        else:
            try:
                parsed = json.loads(result)
                # Extract data array if wrapped in 'data' key
                if isinstance(parsed, dict) and 'data' in parsed:
                    data = parsed['data']
                else:
                    data = parsed if isinstance(parsed, list) else [parsed]
                formatted_text = format_flipcart_info(data)
            except Exception:
                formatted_text = str(result)
    except Exception as e:
        print(f"Error formatting result: {e}")
        formatted_text = str(result)
    
    # Check if no data was found
    if formatted_text is None:
        # Delete the searching message
        try:
            requests.post(BASE_URL + 'deleteMessage', json={
                'chat_id': chat_id,
                'message_id': searching_message_id
            }, timeout=10)
        except Exception as e:
            print(f"Error deleting searching message: {e}")
        
        # Send abusive message with search options
        abusive_msg = choose_no_data_message()
        search_options_text = (
            f"\n\n🔍 Kya dhundna chahte ho bhai?\n"
            f"Neeche se option select kar:"
        )
        
        # Create inline keyboard with search options
        keyboard = {
            "inline_keyboard": [
                [{"text": "🆔 Aadhaar Number", "callback_data": "search_aadhaar"}],
                [{"text": "👤 Name", "callback_data": "search_name"}],
                [{"text": "👨 Father Name", "callback_data": "search_fname"}],
                [{"text": "📱 Mobile Number", "callback_data": "search_mobile"}],
                [{"text": "🏠 Address", "callback_data": "search_address"}],
                [{"text": "📡 Circle", "callback_data": "search_circle"}]
            ]
        }
        
        send_message(chat_id, abusive_msg + search_options_text, reply_markup=keyboard)
        return jsonify({"status": "ok", "action": "no_data_found"})

    # Delete the searching message
    try:
        requests.post(BASE_URL + 'deleteMessage', json={
            'chat_id': chat_id,
            'message_id': searching_message_id
        }, timeout=10)
    except Exception as e:
        print(f"Error deleting searching message: {e}")

    # Send formatted result as a reply to user's message (only once)
    reply_to_user_in_group(chat_id, user_message_id, user, formatted_text)

    return jsonify({"status": "ok", "action": "sent_result"})
    

def is_data_empty(entry):
    """Check if all important fields in an entry are N/A or empty"""
    important_fields = ['id', 'mobile', 'name', 'fname', 'address', 'circle']
    for field in important_fields:
        value = entry.get(field, 'N/A')
        if value and value != 'N/A' and str(value).strip():
            return False
    return True

def format_flipcart_info(data):
    formatted_results = ["ℹ️ Number Information\n"]
    
    # Check if data is empty
    if not data or all(is_data_empty(entry) for entry in data):
        return None  # Signal that no data was found
    
    for idx, entry in enumerate(data):
        result = []
        
        # Start formatting each result
        result.append(f"✨ Result {idx + 1} ✨")
        result.append(f"🆔 Aadhaar No.: {entry.get('id', 'N/A')}")
        result.append(f"📱 Mobile: {entry.get('mobile', 'N/A')}")
        result.append(f"👤 Name: {entry.get('name', 'N/A')}")
        result.append(f"👨 Father_name: {entry.get('fname', 'N/A')}")
        
        # Handle address with formatting
        address = entry.get("address", "N/A")
        address = address.replace("!!", ", ").replace("!", ", ")
        result.append(f"🏠 Address: {address}")
        
        # Handle circle
        result.append(f"📡 Circle: {entry.get('circle', 'N/A')}")
        
        # Add email if available
        if entry.get("email"):
            result.append(f"📧 Email: {entry['email']}")
        
        # Add alt_mobile if available
        if entry.get("alt"):
            result.append(f"📱 Alt_mobile: {entry['alt']}")
        
        # Join the formatted result for this entry and add it to the overall results
        formatted_results.append("\n".join(result))
        formatted_results.append("\n" + "="*50 + "\n")
    
    # Join all formatted results with a newline between them
    return "\n".join(formatted_results)
    

def send_reply(chat_id, text, reply_to_message_id=None):
    """
    Send a reply to a specific message (synchronous helper).
    Returns message_id or None.
    """
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': True
        }
        if reply_to_message_id:
            payload['reply_to_message_id'] = reply_to_message_id

        r = requests.post(BASE_URL + 'sendMessage', json=payload, timeout=10)
        r.raise_for_status()
        return r.json().get('result', {}).get('message_id')
    except Exception as e:
        print("Error sending reply:", e)
        return None


async def reply_to_user(update, context):
    """
    Async handler compatible with python-telegram-bot style handlers.
    Replies to the user's message with a simple echo (or JSON result).
    Use this if you integrate python-telegram-bot; otherwise you can call
    send_reply(...) from the Flask webhook flow.
    """
    try:
        user_message = getattr(update.message, "text", "") or ""
        reply_text = f"You said: {user_message}"

        # If running in a sync environment, run send_reply in executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None,
                                   send_reply,
                                   update.message.chat.id,
                                   reply_text,
                                   update.message.message_id)
    except Exception as e:
        print("reply_to_user error:", e)

def _escape_markdown_v2(text: str) -> str:
    """Escape text for MarkdownV2 (Telegram)"""
    if not isinstance(text, str):
        text = str(text)
    # Characters that must be escaped in MarkdownV2
    # note: backslash must be escaped first
    for ch in ['\\', '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
        text = text.replace(ch, f'\\{ch}')
    return text

def reply_to_user_in_group(chat_id, reply_to_message_id, user, reply_text):
    
    try:
        user_id = user.get('id')
        first_name = user.get('first_name') or user.get('username') or 'User'

        # Escape for MarkdownV2
        esc_name = _escape_markdown_v2(first_name)
        esc_reply = _escape_markdown_v2(reply_text)

        # Build mention using tg://user?id= so it notifies the user
        mention = f'[{esc_name}](tg://user?id={user_id})'
        text = f"{mention}, {esc_reply}"

        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'MarkdownV2',
            'reply_to_message_id': reply_to_message_id,
            'disable_web_page_preview': True
        }
        r = requests.post(BASE_URL + 'sendMessage', json=payload, timeout=10)
        r.raise_for_status()
        return r.json().get('result', {}).get('message_id')
    except Exception as e:
        print("Error replying to user in group:", e)
        return None

def send_document(chat_id, file_bytes, filename, reply_to_message_id=None):
    """
    Send a JSON file (or any file) to the chat as a document.
    file_bytes: bytes or BytesIO
    """
    try:
        url = BASE_URL + 'sendDocument'
        data = {'chat_id': chat_id}
        if reply_to_message_id:
            data['reply_to_message_id'] = reply_to_message_id

        # Ensure we have file-like object
        if isinstance(file_bytes, (bytes, bytearray)):
            file_obj = BytesIO(file_bytes)
        else:
            file_obj = file_bytes

        files = {'document': (filename, file_obj, 'application/json')}
        r = requests.post(url, data=data, files=files, timeout=30)
        r.raise_for_status()
        return r.json().get('result', {}).get('message_id')
    except Exception as e:
        print("Error sending document:", e)
        return None

def handle_callback_query(callback_query):
    """
    Handle inline button clicks (callback queries)
    """
    try:
        query_id = callback_query.get('id')
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        callback_data = callback_query.get('data', '')
        
        # Answer the callback query to remove loading state
        requests.post(BASE_URL + 'answerCallbackQuery', json={
            'callback_query_id': query_id,
            'text': '✅ Samajh gaya!'
        }, timeout=10)
        
        # Prepare response based on selected option
        search_type_map = {
            'search_aadhaar': '🆔 Aadhaar Number',
            'search_name': '👤 Name',
            'search_fname': '👨 Father Name',
            'search_mobile': '📱 Mobile Number',
            'search_address': '🏠 Address',
            'search_circle': '📡 Circle'
        }
        
        search_type = search_type_map.get(callback_data, 'Unknown')
        
        response_text = (
            f"\n{search_type} se search karne ke liye:\n\n"
            f"Abhi yeh feature under development hai bhai! 🚧\n"
            f"Filhal sirf mobile number se hi search kar sakte ho.\n\n"
            f"Agar specific data chahiye toh directly mujhe bolo ya\n"
            f"developer se contact karo! 😎"
        )
        
        send_message(chat_id, response_text)
        
        return jsonify({"status": "ok", "action": "callback_handled"})
        
    except Exception as e:
        print(f"Error handling callback query: {e}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)






