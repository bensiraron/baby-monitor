import os
import logging
from flask import Flask, request
from twilio.rest import Client
from dotenv import load_dotenv
import database

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
database.init_db()

_twilio = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
TWILIO_NUMBER = os.environ['TWILIO_PHONE_NUMBER']

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
    incoming_msg = request.form.get('Body', '').strip()
    sender = request.form.get('From', '')
    logger.info('Incoming message from %s: %r', sender, incoming_msg)

    reply = handle_command(incoming_msg)
    logger.info('Reply: %r', reply)

    _twilio.messages.create(body=reply, from_=TWILIO_NUMBER, to=sender)
    logger.info('Message sent to %s', sender)

    return '', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
