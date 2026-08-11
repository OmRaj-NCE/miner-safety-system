let charts = {};
let selectedMinerId = null;
let audioCtx = null;

function playAudioAlarm() {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        // Resume AudioContext if browser suspended autoplay
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(800, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(400, audioCtx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
        
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.start();
        osc.stop(audioCtx.currentTime + 0.3);
    } catch(e) { 
        console.error("Audio playback error:", e); 
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Unlock Audio Context on first click anywhere on the page
    document.body.addEventListener('click', () => {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }, { once: true });

    updateClock();
    setInterval(updateClock, 1000);

    fetchMiners();
    fetchAlerts();

    // Poll endpoint every 2.5 seconds
    setInterval(() => {
        fetchMiners();
        fetchAlerts();
        if (selectedMinerId) {
            updateModalCharts(selectedMinerId);
        }
    }, 2500);
});

function updateClock() {
    const now = new Date();
    document.getElementById("clock").innerText = now.toUTCString().split(" ")[4] + " UTC";
}

async function fetchMiners() {
    try {
        const res = await fetch("/api/miners");
        const miners = await res.json();
        renderMinerGrid(miners);
        updateSummary(miners);
        updateZoneMap(miners);
    } catch (err) {
        console.error("Failed fetching miners:", err);
    }
}

function renderMinerGrid(miners) {
    const grid = document.getElementById("miner-grid");
    grid.innerHTML = "";

    miners.forEach(m => {
        const card = document.createElement("div");
        card.className = `miner-card ${m.status}`;
        card.onclick = (e) => {
            if (e.target.tagName !== "BUTTON") openModal(m);
        };

        card.innerHTML = `
            <div class="card-header">
                <div>
                    <div class="miner-name">${m.name}</div>
                    <span class="zone-tag">${m.zone}</span>
                </div>
                <div class="risk-gauge">
                    <div class="risk-value">${m.risk_score}%</div>
                    <div class="risk-label">Risk Index</div>
                </div>
            </div>
            <div class="telemetry-list">
                <div class="tel-item"><span>Methane</span>${m.methane_ppm} PPM</div>
                <div class="tel-item"><span>Carbon Monoxide</span>${m.co_ppm} PPM</div>
                <div class="tel-item"><span>Heart Rate</span>${m.heart_rate_bpm} BPM</div>
                <div class="tel-item"><span>Body Temp</span>${m.body_temp_c} °C</div>
            </div>
            <button class="btn-simulate" onclick="simulateIncident(event, ${m.id})">⚠️ Trigger Incident</button>
        `;
        grid.appendChild(card);
    });
}

function updateSummary(miners) {
    let normal = 0, warning = 0, critical = 0;
    miners.forEach(m => {
        if (m.status === 'normal') normal++;
        if (m.status === 'warning') warning++;
        if (m.status === 'critical') critical++;
    });

    document.getElementById("count-normal").innerText = `${normal} Normal`;
    document.getElementById("count-warning").innerText = `${warning} Warning`;
    document.getElementById("count-critical").innerText = `${critical} Critical`;

    const badge = document.getElementById("system-status-badge");
    if (critical > 0) {
        badge.className = "badge badge-critical";
        badge.innerText = `MINE STATUS: CRITICAL (${critical} EMERGENCY)`;
        playAudioAlarm();
    } else {
        badge.className = "badge badge-normal";
        badge.innerText = "MINE STATUS: NOMINAL";
    }
}

function updateZoneMap(miners) {
    ['A', 'B', 'C'].forEach(zoneKey => {
        const zoneMiners = miners.filter(m => m.zone === `Zone ${zoneKey}`);
        const hasCritical = zoneMiners.some(m => m.status === 'critical');
        const hasWarning = zoneMiners.some(m => m.status === 'warning');
        
        const card = document.getElementById(`zone-${zoneKey}`);
        const hazard = document.getElementById(`hazard-zone-${zoneKey}`);
        const minerEl = document.getElementById(`miners-zone-${zoneKey}`);
        
        if (!card) return;
        minerEl.innerText = `Active Personnel: ${zoneMiners.length}`;
        
        if (hasCritical) {
            card.className = "zone-card critical";
            hazard.innerText = "Hazard: EVACUATION ORDER";
            hazard.style.color = "var(--accent-red)";
        } else if (hasWarning) {
            card.className = "zone-card warning";
            hazard.innerText = "Hazard: ELEVATED RISK";
            hazard.style.color = "var(--accent-yellow)";
        } else {
            card.className = "zone-card normal";
            hazard.innerText = "Hazard: NOMINAL";
            hazard.style.color = "var(--accent-green)";
        }
    });
}

async function fetchAlerts() {
    try {
        const res = await fetch("/api/alerts");
        const alerts = await res.json();
        renderAlertFeed(alerts);
        renderAnalyticsTable(alerts);
    } catch (err) {
        console.error("Failed fetching alerts:", err);
    }
}

function renderAlertFeed(alerts) {
    const feed = document.getElementById("alert-feed");
    feed.innerHTML = "";

    if (alerts.length === 0) {
        feed.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No active alerts logged.</div>';
        return;
    }

    alerts.slice(0, 10).forEach(a => {
        const item = document.createElement("div");
        item.className = `alert-item ${a.status}`;
        item.innerHTML = `
            <div class="alert-top">
                <span>${a.miner_name} (${a.zone})</span>
                <span>${a.timestamp.split(' ')[1]}</span>
            </div>
            <div class="alert-msg">${a.recommended_action}</div>
        `;
        feed.appendChild(item);
    });
}

function renderAnalyticsTable(alerts) {
    const tbody = document.getElementById("analytics-tbody");
    if (alerts.length === 0) return;

    tbody.innerHTML = "";
    alerts.forEach(a => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>#${a.id}</td>
            <td>${a.timestamp}</td>
            <td>${a.miner_name}</td>
            <td>${a.zone}</td>
            <td style="font-weight:bold; color: ${a.status === 'critical' ? '#ef4444' : '#f59e0b'}">${a.risk_score}%</td>
            <td><span class="pill pill-${a.status === 'critical' ? 'red' : 'yellow'}">${a.status.toUpperCase()}</span></td>
            <td>${a.recommended_action}</td>
        `;
        tbody.appendChild(row);
    });
}

async function simulateIncident(event, minerId) {
    event.stopPropagation();
    try {
        await fetch(`/api/simulate-incident/${minerId}`, { method: "POST" });
        fetchMiners();
    } catch (err) {
        console.error("Failed initiating incident:", err);
    }
}

async function resetSystem() {
    if (confirm("Reset simulation state and clear incident logs?")) {
        try {
            await fetch('/api/reset-simulation', { method: 'POST' });
            fetchMiners();
            fetchAlerts();
        } catch (err) {
            console.error("Failed resetting system:", err);
        }
    }
}

/* Modal and Charting Logic */
function openModal(miner) {
    selectedMinerId = miner.id;
    document.getElementById("modal-miner-name").innerText = miner.name;
    document.getElementById("modal-miner-zone").innerText = miner.zone;
    document.getElementById("modal-action-text").innerText = miner.recommended_action;
    document.getElementById("miner-modal").style.display = "flex";

    initModalCharts();
    updateModalCharts(miner.id);
}

function closeModal() {
    document.getElementById("miner-modal").style.display = "none";
    selectedMinerId = null;
}

function initModalCharts() {
    const config = (label, color) => ({
        type: 'line',
        data: { labels: [], datasets: [{ label, data: [], borderColor: color, fill: false, tension: 0.3 }] },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#8a99ad', font: { size: 9 } } },
                y: { ticks: { color: '#8a99ad', font: { size: 9 } } }
            }
        }
    });

    ['methane', 'co', 'hr', 'temp'].forEach(metric => {
        if (charts[metric]) charts[metric].destroy();
    });

    charts.methane = new Chart(document.getElementById('chart-methane'), config('Methane', '#f59e0b'));
    charts.co = new Chart(document.getElementById('chart-co'), config('CO', '#ef4444'));
    charts.hr = new Chart(document.getElementById('chart-hr'), config('HR', '#10b981'));
    charts.temp = new Chart(document.getElementById('chart-temp'), config('Temp', '#3b82f6'));
}

async function updateModalCharts(minerId) {
    try {
        const res = await fetch(`/api/miner/${minerId}/history`);
        const history = await res.json();

        const timestamps = history.map(h => h.timestamp);
        
        charts.methane.data.labels = timestamps;
        charts.methane.data.datasets[0].data = history.map(h => h.methane_ppm);
        charts.methane.update();

        charts.co.data.labels = timestamps;
        charts.co.data.datasets[0].data = history.map(h => h.co_ppm);
        charts.co.update();

        charts.hr.data.labels = timestamps;
        charts.hr.data.datasets[0].data = history.map(h => h.heart_rate_bpm);
        charts.hr.update();

        charts.temp.data.labels = timestamps;
        charts.temp.data.datasets[0].data = history.map(h => h.body_temp_c);
        charts.temp.update();
    } catch (err) {
        console.error("Failed fetching history for charts:", err);
    }
}