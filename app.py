import os
from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import database

load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
_validator = RequestValidator(os.environ['TWILIO_AUTH_TOKEN'])
database.init_db()

REGISTRATION = {
    'הנקה': ('🤱', 'הנקה נרשמה'),
    'פיפי': ('🚼', 'חיתול פיפי נרשם'),
    'קקי':  ('💩', 'חיתול קקי נרשם'),
}

HELP_TEXT = (
    '❓ פקודה לא מוכרת.\n\n'
    'הפקודות הזמינות:\n'
    '• הנקה — רישום הנקה\n'
    '• פיפי — רישום חיתול פיפי\n'
    '• קקי — רישום חיתול קקי\n'
    '• אחרון — הרישום האחרון בכל קטגוריה\n'
    '• דוח — סיכום 24 שעות אחרונות\n'
    '• דוח מורחב — סיכום 3 ימים אחרונים\n'
    '• מחק אחרון — מחיקת הרשומה האחרונה\n'
    '• מחק הכל — מחיקת כל הרשומות'
)


def handle_command(text: str) -> str:
    text = text.strip()

    if text in REGISTRATION:
        emoji, label = REGISTRATION[text]
        israel_time = database.log_event(text)
        return f'✅ {emoji} {label} בשעה {israel_time.strftime("%H:%M")}'

    if text == 'אחרון':
        return database.get_last_events()

    if text == 'דוח':
        return database.get_report()

    if text == 'דוח מורחב':
        return database.get_extended_report()

    if text == 'מחק אחרון':
        result = database.delete_last_event()
        if result is None:
            return '❌ אין רשומות למחיקה.'
        event_type, dt = result
        emoji = database.EMOJIS[event_type]
        return f'🗑️ נמחקה הרשומה האחרונה: {emoji} {event_type} מ-{dt.strftime("%d/%m/%Y")} בשעה {dt.strftime("%H:%M")}'

    if text == 'מחק הכל':
        count = database.delete_all_events()
        if count == 0:
            return '❌ אין רשומות למחיקה.'
        return f'🗑️ נמחקו {count} רשומות. מסד הנתונים ריק.'

    return HELP_TEXT


@app.route('/webhook', methods=['POST'])
def webhook():
    url = request.url
    signature = request.headers.get('X-Twilio-Signature', '')
    if not _validator.validate(url, request.form, signature):
        abort(403)

    incoming_msg = request.form.get('Body', '').strip()
    response = MessagingResponse()
    response.message(handle_command(incoming_msg))
    return str(response)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
