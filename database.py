import os
import sqlite3
from datetime import datetime, timedelta, time as dt_time
import pytz

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')
DB_PATH = os.environ.get('DB_PATH', 'baby_monitor.db')

EVENTS = ['הנקה', 'פיפי', 'קקי']
EMOJIS = {'הנקה': '🤱', 'פיפי': '🚼', 'קקי': '💩'}
COUNT_LABELS = {'הנקה': 'מספר הנקות', 'פיפי': 'מספר פעמים', 'קקי': 'מספר פעמים'}
INTERVAL_LABELS = {
    'הנקה': 'ממוצע זמן בין הנקה להנקה',
    'פיפי': 'ממוצע זמן בין פיפי לפיפי',
    'קקי': 'ממוצע זמן בין קקי לקקי',
}
HEBREW_DAYS = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def _now_utc() -> datetime:
    return datetime.now(pytz.utc)


def _ts_to_str(dt: datetime) -> str:
    return dt.astimezone(pytz.utc).strftime('%Y-%m-%d %H:%M:%S.%f')


def _str_to_israel(ts_str: str) -> datetime:
    dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f')
    return pytz.utc.localize(dt).astimezone(ISRAEL_TZ)


def log_event(event_type: str) -> datetime:
    now = _now_utc()
    conn = _get_conn()
    conn.execute(
        'INSERT INTO events (event_type, timestamp) VALUES (?, ?)',
        (event_type, _ts_to_str(now))
    )
    conn.commit()
    conn.close()
    return now.astimezone(ISRAEL_TZ)


def _format_duration(total_minutes: float) -> str:
    minutes = int(round(total_minutes))
    h, m = divmod(minutes, 60)
    if h == 0:
        return f'{m} דקות'
    if m == 0:
        return f'{h} שעות'
    return f'{h} שעות {m} דקות'


def _calc_avg_interval(timestamps: list) -> str:
    if len(timestamps) < 2:
        return 'אין מספיק נתונים'
    intervals = [
        (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
        for i in range(1, len(timestamps))
    ]
    return _format_duration(sum(intervals) / len(intervals))


def _format_section(event_type: str, timestamps: list) -> str:
    emoji = EMOJIS[event_type]
    if not timestamps:
        return f'{emoji} {event_type}:\n  אין רישומים'
    times_str = ', '.join(ts.strftime('%H:%M') for ts in timestamps)
    count = len(timestamps)
    avg = _calc_avg_interval(timestamps)
    return (
        f'{emoji} {event_type}:\n'
        f'  {times_str}\n'
        f'  {COUNT_LABELS[event_type]}: {count}\n'
        f'  {INTERVAL_LABELS[event_type]}: {avg}'
    )


def get_last_events() -> str:
    conn = _get_conn()
    lines = []
    for event_type in EVENTS:
        row = conn.execute(
            'SELECT timestamp FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1',
            (event_type,)
        ).fetchone()
        emoji = EMOJIS[event_type]
        if row:
            dt = _str_to_israel(row['timestamp'])
            lines.append(f'{emoji} {event_type}: {dt.strftime("%d/%m/%Y")} בשעה {dt.strftime("%H:%M")}')
        else:
            lines.append(f'{emoji} {event_type}: אין רישומים')
    conn.close()
    return '\n'.join(lines)


def get_report() -> str:
    since_str = _ts_to_str(_now_utc() - timedelta(hours=24))
    conn = _get_conn()
    sections = []
    for event_type in EVENTS:
        rows = conn.execute(
            'SELECT timestamp FROM events WHERE event_type = ? AND timestamp >= ? ORDER BY timestamp ASC',
            (event_type, since_str)
        ).fetchall()
        timestamps = [_str_to_israel(row['timestamp']) for row in rows]
        sections.append(_format_section(event_type, timestamps))
    conn.close()
    return '📊 דוח 24 שעות אחרונות:\n\n' + '\n\n'.join(sections)


def delete_all_events() -> int:
    conn = _get_conn()
    count = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    conn.execute('DELETE FROM events')
    conn.commit()
    conn.close()
    return count


def delete_last_event() -> tuple | None:
    conn = _get_conn()
    row = conn.execute(
        'SELECT id, event_type, timestamp FROM events ORDER BY timestamp DESC LIMIT 1'
    ).fetchone()
    if row is None:
        conn.close()
        return None
    conn.execute('DELETE FROM events WHERE id = ?', (row['id'],))
    conn.commit()
    conn.close()
    return row['event_type'], _str_to_israel(row['timestamp'])


def delete_last_event_by_type(event_type: str) -> datetime | None:
    conn = _get_conn()
    row = conn.execute(
        'SELECT id, timestamp FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1',
        (event_type,)
    ).fetchone()
    if row is None:
        conn.close()
        return None
    conn.execute('DELETE FROM events WHERE id = ?', (row['id'],))
    conn.commit()
    conn.close()
    return _str_to_israel(row['timestamp'])


def get_dashboard_data() -> dict:
    since_str = _ts_to_str(_now_utc() - timedelta(hours=24))
    conn = _get_conn()
    result = {}
    for event_type in EVENTS:
        rows = conn.execute(
            'SELECT timestamp FROM events WHERE event_type = ? AND timestamp >= ? ORDER BY timestamp ASC',
            (event_type, since_str)
        ).fetchall()
        timestamps = [_str_to_israel(row['timestamp']) for row in rows]

        last_row = conn.execute(
            'SELECT timestamp FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT 1',
            (event_type,)
        ).fetchone()
        last = _str_to_israel(last_row['timestamp']) if last_row else None

        result[event_type] = {
            'times': [ts.strftime('%H:%M') for ts in timestamps],
            'count': len(timestamps),
            'avg_interval': _calc_avg_interval(timestamps),
            'last': last.strftime('%d/%m %H:%M') if last else None,
        }
    conn.close()
    return result


def get_extended_report() -> str:
    today = _now_utc().astimezone(ISRAEL_TZ).date()
    conn = _get_conn()
    day_sections = []

    for i in range(2, -1, -1):
        day = today - timedelta(days=i)
        day_start_il = ISRAEL_TZ.localize(datetime.combine(day, dt_time.min))
        day_end_il = day_start_il + timedelta(days=1)
        start_str = _ts_to_str(day_start_il)
        end_str = _ts_to_str(day_end_il)

        if i == 0:
            header = f'📅 היום ({day.strftime("%d/%m/%Y")}):'
        elif i == 1:
            header = f'📅 אתמול ({day.strftime("%d/%m/%Y")}):'
        else:
            day_name = HEBREW_DAYS[day.weekday()]
            header = f'📅 {day.strftime("%d/%m/%Y")} (יום {day_name}):'

        sections = []
        for event_type in EVENTS:
            rows = conn.execute(
                'SELECT timestamp FROM events WHERE event_type = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC',
                (event_type, start_str, end_str)
            ).fetchall()
            timestamps = [_str_to_israel(row['timestamp']) for row in rows]
            sections.append(_format_section(event_type, timestamps))

        day_sections.append(header + '\n' + '\n\n'.join(sections))

    conn.close()
    return '📊 דוח מורחב - 3 ימים אחרונים:\n\n' + '\n\n---\n\n'.join(day_sections)
