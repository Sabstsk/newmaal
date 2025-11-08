from flask import Flask, request, jsonify
import requests
import os
import json
import html
from dotenv import load_dotenv
import asyncio
import re
import random

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

    # Prepare JSON text for display & copy button
    if isinstance(result, (dict, list)):
        json_text = json.dumps(result, indent=2, ensure_ascii=False)
    else:
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

    # After sending/editing the result, reply to that user's message in the group
    # (place this where you finalize sending result)
    if text.isdigit() and len(text) == 10:
        # ...existing send/search/edit logic ...
        # assume `searching_message_id` and `success` variables as in existing flow
        # after you edited the searching message with the JSON result:
        if success:
            # short reply telling user where result is
            reply_text = "Result sent above. Use the \"Copy JSON\" button to copy the data."
            reply_to_user_in_group(chat_id, user_message_id, user, reply_text)
        else:
            # if fallback sent a normal message (send_message returned a message id)
            reply_text = "Result sent as a message. Use the Copy JSON button if available."
            reply_to_user_in_group(chat_id, user_message_id, user, reply_text)

    return jsonify({"status": "ok", "action": "sent_result"})
    

def beautify_json(json_data):

    try:
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        # Beautify the JSON and return the indented version
        return json.dumps(json_data, indent=4)
    
    except (ValueError, TypeError) as e:
        # Handle invalid JSON input
        return f"Error beautifying JSON: {e}"
    

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
    """
    Reply to a specific user's message in a group with a clickable mention (MarkdownV2).
    - user: dict from update['message']['from']
    - reply_text: plain string (will be escaped)
    This will mention the user so they get notified that the bot replied to them.
    """
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

if __name__ == '__main__':
    app.run(debug=True)






