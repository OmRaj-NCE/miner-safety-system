import sqlite3
import time
import random
from datetime import datetime

DB_NAME = 'miner_safety.db'

INITIAL_MINERS = [
    (1, 'Alex Vance', 'Zone A'),
    (2, 'Sarah Jenkins', 'Zone A'),
    (3, 'Marcus Brody', 'Zone B'),
    (4, 'Elena Rostova', 'Zone B'),
    (5, 'David Chen', 'Zone C'),
    (6, 'Jamal Kwame', 'Zone C')
]

incident_triggers = {}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS miners (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            zone TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id INTEGER,
            methane_ppm REAL,
            co_ppm REAL,
            heart_rate_bpm REAL,
            body_temp_c REAL,
            timestamp DATETIME,
            FOREIGN KEY (miner_id) REFERENCES miners (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id INTEGER,
            risk_score REAL,
            status TEXT,
            recommended_action TEXT,
            timestamp DATETIME
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM miners")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO miners VALUES (?, ?, ?)", INITIAL_MINERS)
        
    conn.commit()
    conn.close()

sensor_state = {
    m[0]: {
        'methane': random.uniform(10, 40),
        'co': random.uniform(1, 8),
        'hr': random.uniform(68, 82),
        'temp': random.uniform(36.4, 36.8)
    } for m in INITIAL_MINERS
}

def trigger_incident(miner_id):
    incident_triggers[miner_id] = 1

def generate_sensor_tick():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for miner in INITIAL_MINERS:
        m_id = miner[0]
        state = sensor_state[m_id]

        if m_id in incident_triggers:
            step = incident_triggers[m_id]
            # Rapid aggressive jump on first 2 ticks to trigger high risk immediately
            state['methane'] += random.uniform(400, 600)
            state['co'] += random.uniform(90, 130)
            state['hr'] += random.uniform(20, 35)
            state['temp'] += random.uniform(0.8, 1.4)
            
            incident_triggers[m_id] += 1
            if step > 10:
                incident_triggers.pop(m_id, None)
        else:
            state['methane'] = max(0, min(80, state['methane'] + random.uniform(-2, 2)))
            state['co'] = max(0, min(15, state['co'] + random.uniform(-0.5, 0.5)))
            state['hr'] = max(55, min(100, state['hr'] + random.uniform(-1.5, 1.5)))
            state['temp'] = max(36.0, min(37.2, state['temp'] + random.uniform(-0.05, 0.05)))

        cursor.execute('''
            INSERT INTO readings (miner_id, methane_ppm, co_ppm, heart_rate_bpm, body_temp_c, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (m_id, round(state['methane'], 2), round(state['co'], 2), 
              round(state['hr'], 1), round(state['temp'], 2), now))

    conn.commit()
    conn.close()