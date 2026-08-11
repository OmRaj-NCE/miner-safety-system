import sqlite3
import joblib
import numpy as np
import pandas as pd
import csv
import io
import random
from datetime import datetime
from flask import Flask, jsonify, render_template, request, Response
from apscheduler.schedulers.background import BackgroundScheduler
import simulator

app = Flask(__name__)

# Initialize Database & Simulator State
simulator.init_db()

# Load pretrained ML model
try:
    risk_model = joblib.load('risk_model.pkl')
    print("[✔] Loaded ML model successfully.")
except Exception as e:
    print("[!] Failed to load risk_model.pkl. Run `python train_model.py` first.")

def compute_risk(methane, co, hr, temp):
    # Pass features as DataFrame with explicit column names to eliminate scikit-learn warnings
    features = pd.DataFrame([{
        'methane_ppm': methane,
        'co_ppm': co,
        'heart_rate_bpm': hr,
        'body_temp_c': temp
    }])
    
    probabilities = risk_model.predict_proba(features)[0]
    
    # Continuous metric calculation derived from class probabilities
    # Classes: 0 = Low Risk, 1 = Medium Risk, 2 = High Risk
    risk_score = (probabilities[1] * 50) + (probabilities[2] * 100)
    risk_score = round(float(np.clip(risk_score, 0, 100)), 1)

    if risk_score > 70:
        status = 'critical'
    elif risk_score >= 40:
        status = 'warning'
    else:
        status = 'normal'

    # Prescriptive Safety Rules based on dominant metrics
    if status == 'critical':
        if (methane > 800 or co > 180) and (hr > 110 or temp > 38.5):
            rec = "CRITICAL: Evacuate Zone & Dispatch Medical Unit Immediately"
        elif methane > 800 or co > 180:
            rec = "CRITICAL: Gas Leak Detected - Evacuate Zone Immediately"
        else:
            rec = "CRITICAL: Severe Vitals Distress - Dispatch Medic to Miner"
    elif status == 'warning':
        if methane > 400 or co > 80:
            rec = "WARNING: Elevated Gas Levels - Inspect Ventilation Shafts"
        else:
            rec = "WARNING: Elevated Vitals - Instruct Miner to Take Rest Break"
    else:
        rec = "Nominal Conditions — Standard Monitoring"

    return risk_score, status, rec

def process_latest_readings_and_alerts():
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.miner_id, r.methane_ppm, r.co_ppm, r.heart_rate_bpm, r.body_temp_c, r.timestamp
        FROM readings r
        INNER JOIN (
            SELECT miner_id, MAX(id) as max_id FROM readings GROUP BY miner_id
        ) latest ON r.id = latest.max_id
    ''')
    readings = cursor.fetchall()

    for r in readings:
        m_id, methane, co, hr, temp, ts = r
        score, status, action = compute_risk(methane, co, hr, temp)

        if status in ['warning', 'critical']:
            cursor.execute('''
                SELECT timestamp FROM alerts WHERE miner_id = ? ORDER BY id DESC LIMIT 1
            ''', (m_id,))
            last_alert = cursor.fetchone()

            should_insert = True
            if last_alert:
                last_time = datetime.strptime(last_alert[0], '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - last_time).total_seconds() < 10:
                    should_insert = False

            if should_insert:
                cursor.execute('''
                    INSERT INTO alerts (miner_id, risk_score, status, recommended_action, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (m_id, score, status, action, ts))

    conn.commit()
    conn.close()

def background_task():
    simulator.generate_sensor_tick()
    process_latest_readings_and_alerts()

# Start background simulation scheduler (tick every 3 seconds)
scheduler = BackgroundScheduler()
scheduler.add_job(func=background_task, trigger="interval", seconds=3)
scheduler.start()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/miners')
def get_miners():
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, zone FROM miners')
    miners_info = cursor.fetchall()

    response = []
    for m in miners_info:
        m_id, name, zone = m
        cursor.execute('''
            SELECT methane_ppm, co_ppm, heart_rate_bpm, body_temp_c, timestamp 
            FROM readings WHERE miner_id = ? ORDER BY id DESC LIMIT 1
        ''', (m_id,))
        last_r = cursor.fetchone()

        if last_r:
            methane, co, hr, temp, ts = last_r
            score, status, action = compute_risk(methane, co, hr, temp)
            response.append({
                'id': m_id,
                'name': name,
                'zone': zone,
                'methane_ppm': methane,
                'co_ppm': co,
                'heart_rate_bpm': hr,
                'body_temp_c': temp,
                'risk_score': score,
                'status': status,
                'recommended_action': action,
                'timestamp': ts
            })

    conn.close()
    return jsonify(response)

@app.route('/api/miner/<int:miner_id>/history')
def get_miner_history(miner_id):
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT methane_ppm, co_ppm, heart_rate_bpm, body_temp_c, timestamp 
        FROM readings WHERE miner_id = ? ORDER BY id DESC LIMIT 30
    ''', (miner_id,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in reversed(rows):
        history.append({
            'methane_ppm': row[0],
            'co_ppm': row[1],
            'heart_rate_bpm': row[2],
            'body_temp_c': row[3],
            'timestamp': row[4].split(' ')[1]
        })
    return jsonify(history)

@app.route('/api/alerts')
def get_alerts():
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, a.miner_id, m.name, m.zone, a.risk_score, a.status, a.recommended_action, a.timestamp
        FROM alerts a
        JOIN miners m ON a.miner_id = m.id
        ORDER BY a.id DESC LIMIT 20
    ''')
    rows = cursor.fetchall()
    conn.close()

    alerts = []
    for r in rows:
        alerts.append({
            'id': r[0],
            'miner_id': r[1],
            'miner_name': r[2],
            'zone': r[3],
            'risk_score': r[4],
            'status': r[5],
            'recommended_action': r[6],
            'timestamp': r[7]
        })
    return jsonify(alerts)

@app.route('/api/simulate-incident/<int:miner_id>', methods=['POST'])
def trigger_incident_route(miner_id):
    simulator.trigger_incident(miner_id)
    # Force an immediate sensor tick so frontend metrics shift instantly
    background_task()
    return jsonify({'status': 'success', 'message': f'Incident sequence initiated for Miner #{miner_id}'})

@app.route('/api/export-alerts')
def export_alerts():
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, a.timestamp, m.name, m.zone, a.risk_score, a.status, a.recommended_action
        FROM alerts a JOIN miners m ON a.miner_id = m.id
        ORDER BY a.id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Incident ID', 'Timestamp', 'Miner Name', 'Zone', 'Risk Score (%)', 'Severity', 'Action Recommended'])
    for r in rows:
        writer.writerow(r)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=miner_safety_incidents.csv"}
    )

@app.route('/api/reset-simulation', methods=['POST'])
def reset_simulation():
    conn = sqlite3.connect('miner_safety.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM readings')
    cursor.execute('DELETE FROM alerts')
    conn.commit()
    conn.close()
    
    simulator.incident_triggers.clear()
    for m_id in simulator.sensor_state:
        simulator.sensor_state[m_id] = {
            'methane': random.uniform(10, 40),
            'co': random.uniform(1, 8),
            'hr': random.uniform(68, 82),
            'temp': random.uniform(36.4, 36.8)
        }
    return jsonify({'status': 'reset complete'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)