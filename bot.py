from flask import Flask, request, jsonify
import requests
import os
import json
import html
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
API_KEY=os.getenv('API_KEY')
OSINT_BASE_URL = os.getenv('OSINT_BASE_URL')
BASE_URL = f'https://api.telegram.org/bot{API_TOKEN}/'

# required group (provided)
REQUIRED_GROUP_ID = os.getenv('REQUIRED_GROUP_ID', '2925002298')
REQUIRED_GROUP_INVITE = os.getenv('REQUIRED_GROUP_LINK', 'https://t.me/+oCWGUjOqlgM3ZGRl')

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

# modify send_message to accept optional reply_markup
def send_message(chat_id, text, reply_markup=None):
    """Send message to Telegram chat and return message_id"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': True
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        response = requests.post(BASE_URL + 'sendMessage', json=payload)
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
            return "Error: OSINT_BASE_URL not configured"

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
            return beautify_json(resp.json())
        except ValueError:
            return resp.text or "No content"

    except Exception as e:
        print("Error fetching data:", e)
        return f"Error fetching data: {e}"

def is_user_in_group(user_id):
    """
    Return True only if the user is a member of REQUIRED_GROUP_ID.
    If getChatMember returns non-200 or an error occurs, treat as NOT a member (return False)
    so users must join the group to use the bot.
    """
    try:
        resp = requests.get(
            BASE_URL + 'getChatMember',
            params={'chat_id': REQUIRED_GROUP_ID, 'user_id': user_id},
            timeout=8
        )
        # If Telegram responds with non-200, user is not verified -> treat as not a member
        if resp.status_code != 200:
            print("getChatMember non-200:", resp.status_code, resp.text)
            return False

        data = resp.json()
        status = data.get('result', {}).get('status', '')
        print("getChatMember status:", status)

        # Acceptable statuses that indicate membership
        return status in ('creator', 'administrator', 'member', 'restricted')

    except requests.HTTPError as e:
        print("getChatMember HTTPError:", e, getattr(e, 'response', None))
        return False
    except Exception as e:
        print("is_user_in_group error:", e)
        # Enforce join on unexpected errors
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json() or {}
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type", "")
    user = message.get("from") or {}
    user_id = user.get("id")

    if not chat_id or not user_id:
        return jsonify({"status": "ignored"})

    # If message in private chat, require membership in REQUIRED_GROUP_ID
    if chat_type == "private":
        if not is_user_in_group(user_id):
            text = (
                "⚠️ You must join the support group to use this bot.\n\n"
                "Please join the group and then send /start or your 10-digit number."
            )
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "Join Group to Use Bot", "url": REQUIRED_GROUP_INVITE}
                    ]
                ]
            }
            send_message(chat_id, text, reply_markup=reply_markup)
            return jsonify({"status": "need_join"})

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
            
            # Prepare JSON text for display & copy button
            if isinstance(result, (dict, list)):
                json_text = json.dumps(result, indent=2, ensure_ascii=False)
            else:
                # If get_phone_info returned a plain string, try to parse as JSON, otherwise use as-is
                try:
                    parsed = json.loads(result)
                    json_text = json.dumps(parsed, indent=2, ensure_ascii=False)
                except Exception:
                    json_text = str(result)

            # Telegram message limit ~4096 chars — trim for display/copy if needed
            MAX_COPY = 4000
            if len(json_text) > MAX_COPY:
                display_text = json_text[:MAX_COPY] + "\n\n[...truncated]"
                copy_text = json_text[:MAX_COPY]
            else:
                display_text = json_text
                copy_text = json_text

            # Escape for HTML <pre> block
            escaped = html.escape(display_text)
            pre_text = f"<pre>{escaped}</pre>"

            # Inline button that inserts the JSON into the user's current chat input (user can then copy)
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "Copy JSON",
                            "switch_inline_query_current_chat": copy_text
                        }
                    ]
                ]
            }

            # 3. Edit the original "Searching" message with the final result as code block + copy button
            success = edit_message_text(chat_id, searching_message_id, pre_text, parse_mode='HTML', reply_markup=reply_markup)
            if not success:
                # fallback: send as a normal message
                send_message(chat_id, pre_text)
            
        else:
            # Send a friendly message if input is invalid
            send_message(chat_id, "⚠️ Abe Bsdk phone number bhej")

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
    return json.loads(s.replace('MRX', 'CRAZYPANEL1')) if isinstance(data, (dict, list)) else s.replace('MRX', 'CRAZYPANEL1')

if __name__ == '__main__':
    app.run(debug=True)






