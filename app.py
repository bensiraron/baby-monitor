import os
from flask import Flask, request, jsonify, render_template
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import database

load_dotenv()

app = Flask(__name__)
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
    incoming_msg = request.form.get('Body', '').strip()
    response = MessagingResponse()
    response.message(handle_command(incoming_msg))
    return str(response)


@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/data')
def api_data():
    return jsonify(database.get_dashboard_data())


@app.route('/api/log/<event_type>', methods=['POST'])
def api_log(event_type):
    if event_type not in database.EVENTS:
        return jsonify({'message': 'סוג אירוע לא חוקי'}), 400
    israel_time = database.log_event(event_type)
    emoji = database.EMOJIS[event_type]
    return jsonify({'message': f'✅ {emoji} {event_type} נרשם בשעה {israel_time.strftime("%H:%M")}'})


@app.route('/api/delete-last/<event_type>', methods=['POST'])
def api_delete_last(event_type):
    if event_type not in database.EVENTS:
        return jsonify({'message': 'סוג אירוע לא חוקי'}), 400
    dt = database.delete_last_event_by_type(event_type)
    if dt is None:
        return jsonify({'message': f'❌ אין רשומות {event_type} למחיקה'})
    emoji = database.EMOJIS[event_type]
    return jsonify({'message': f'🗑️ נמחק {emoji} {event_type} מ-{dt.strftime("%H:%M")}'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
