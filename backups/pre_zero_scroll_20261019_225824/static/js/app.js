document.addEventListener('DOMContentLoaded', () => {
    SieisCharts.initCharts();
    
    // Initial fetch and start recurring poll loop (every 3 seconds)
    fetchDashboardData();
    setInterval(fetchDashboardData, 3000);

    // Limit select listener
    const limitSelect = document.getElementById('history-limit-select');
    if (limitSelect) {
        limitSelect.addEventListener('change', () => fetchDashboardData());
    }

    // Refresh serial ports list
    refreshSerialPorts();
});

let isDemoRunning = false;
let isSerialConnected = false;

async function toggleDemoStream() {
    const btn = document.getElementById('btn-toggle-demo');
    if (!isDemoRunning) {
        const res = await fetch('/api/demo/start', { method: 'POST' });
        if (res.ok) {
            isDemoRunning = true;
            btn.textContent = '⏹️ Pause Demo';
            btn.className = 'btn btn-danger';
        }
    } else {
        const res = await fetch('/api/demo/stop', { method: 'POST' });
        if (res.ok) {
            isDemoRunning = false;
            btn.textContent = '▶️ Start Demo Stream';
            btn.className = 'btn btn-primary';
        }
    }
    fetchDashboardData();
}

async function triggerDemoEvent(eventMode) {
    await fetch('/api/demo/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: eventMode })
    });
    fetchDashboardData();
}

async function refreshSerialPorts() {
    try {
        const res = await fetch('/api/serial/ports');
        if (res.ok) {
            const data = await res.json();
            const select = document.getElementById('serial-port-select');
            if (select && data.ports && data.ports.length > 0) {
                select.innerHTML = data.ports.map(p => `<option value="${p}">${p}</option>`).join('');
            }
        }
    } catch (e) {
        console.debug('Serial ports fetch:', e);
    }
}

async function toggleSerialBridge() {
    const btn = document.getElementById('btn-toggle-serial');
    const port = document.getElementById('serial-port-select')?.value || 'COM4';

    if (!isSerialConnected) {
        const res = await fetch('/api/serial/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port })
        });
        if (res.ok) {
            isSerialConnected = true;
            btn.textContent = `Disconnect (${port})`;
            btn.className = 'btn btn-active';
        }
    } else {
        const res = await fetch('/api/serial/disconnect', { method: 'POST' });
        if (res.ok) {
            isSerialConnected = false;
            btn.textContent = `Connect USB (${port})`;
            btn.className = 'btn btn-outline';
        }
    }
    fetchDashboardData();
}

async function fetchDashboardData() {
    try {
        const limit = document.getElementById('history-limit-select')?.value || 60;
        
        // Parallel fetch for snappy responsiveness
        const [statsRes, readingsRes, alertsRes, recsRes, fcRes] = await Promise.all([
            fetch('/api/stats'),
            fetch(`/api/readings?limit=${limit}`),
            fetch('/api/alerts?limit=10'),
            fetch('/api/recommendations'),
            fetch('/api/forecast')
        ]);

        if (statsRes.ok) {
            const statsData = await statsRes.json();
            updateSystemHeader(statsData);
            updateScores(statsData.latest_score);
            updateLiveSensors(statsData.latest_observation, statsData.mq135_baseline_mv);
        }

        if (readingsRes.ok && statsRes.ok) {
            const readingsData = await readingsRes.json();
            const statsData = await statsRes.json();
            SieisCharts.updateCharts(readingsData.readings, statsData.mq135_baseline_mv);
            
            // Build score trends if available in readings
            const labels = [];
            const ehsList = [];
            const comfList = [];
            readingsData.readings.forEach(r => {
                if (r.received_at) {
                    const d = new Date(r.received_at);
                    labels.push(d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
                    // If scores are saved alongside or derived:
                    ehsList.push(r.temperature_c ? Math.min(100, Math.max(30, 100 - Math.abs(r.temperature_c - 22.5) * 4)) : null);
                    comfList.push(r.temperature_c && r.humidity_percent ? 90 : null);
                }
            });
        }

        if (alertsRes.ok) {
            const alertsData = await alertsRes.json();
            updateAlerts(alertsData.alerts);
        }

        if (recsRes.ok) {
            const recsData = await recsRes.json();
            updateRecommendations(recsData.recommendations);
        }

        if (fcRes.ok) {
            const fcData = await fcRes.json();
            updateForecasts(fcData);
        }

    } catch (err) {
        console.warn('Telemetry polling error:', err);
        setDisconnectedState();
    }
}

function updateSystemHeader(statsData) {
    const pill = document.getElementById('device-pill');
    const text = document.getElementById('device-status-text');
    const timeDisplay = document.getElementById('last-seen-time');
    const banner = document.getElementById('staleness-banner');

    const freshness = statsData.freshness;
    if (freshness && freshness.is_connected && !freshness.is_stale) {
        pill.className = 'status-pill connected';
        text.textContent = 'Node Live (COM4 / Wi-Fi)';
        banner.classList.add('hidden');
    } else if (freshness && freshness.is_stale) {
        pill.className = 'status-pill stale';
        text.textContent = `Telemetry Stale (${freshness.seconds_since_last}s ago)`;
        banner.classList.remove('hidden');
    } else {
        pill.className = 'status-pill disconnected';
        text.textContent = 'Node Offline';
        banner.classList.remove('hidden');
    }

    if (freshness && freshness.last_seen_at) {
        const d = new Date(freshness.last_seen_at);
        timeDisplay.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
}

function updateScores(scoreData) {
    if (!scoreData) return;

    // Environmental Health Score
    const ehsVal = document.getElementById('ehs-score-val');
    const ehsGrade = document.getElementById('ehs-grade-badge');
    const ehsReason = document.getElementById('ehs-reason');
    const ehsCoverage = document.getElementById('ehs-coverage');

    if (scoreData.health_score !== null && scoreData.health_score !== undefined) {
        ehsVal.textContent = Math.round(scoreData.health_score);
        ehsGrade.textContent = scoreData.health_grade || 'UNKNOWN';
        ehsGrade.className = `grade-badge grade-${(scoreData.health_grade || 'optimal').toLowerCase()}`;
        ehsReason.textContent = scoreData.calculation_reason || 'Multi-sensor context healthy.';
        ehsCoverage.textContent = `${scoreData.data_coverage_pct || 100}% Coverage`;
    }

    // Subcomponents
    const comps = scoreData.components || {};
    setMeter('bar-comfort', 'val-comfort', comps.comfort);
    setMeter('bar-gas', 'val-gas', comps.gas_response);
    setMeter('bar-light', 'val-light', comps.lighting);
    setMeter('bar-noise', 'val-noise', comps.noise);

    // Comfort Index
    const comfortVal = document.getElementById('comfort-score-val');
    const comfortStatus = document.getElementById('comfort-status-badge');
    if (scoreData.comfort_index !== null && scoreData.comfort_index !== undefined) {
        comfortVal.textContent = Math.round(scoreData.comfort_index);
        comfortStatus.textContent = scoreData.comfort_status || 'PENDING';
        comfortStatus.className = `grade-badge grade-${scoreData.comfort_index >= 85 ? 'optimal' : scoreData.comfort_index >= 65 ? 'fair' : 'poor'}`;
    }
}

function setMeter(barId, valId, score) {
    const bar = document.getElementById(barId);
    const val = document.getElementById(valId);
    if (!bar || !val) return;
    if (score !== null && score !== undefined) {
        bar.style.width = `${Math.min(100, Math.max(0, score))}%`;
        val.textContent = `${Math.round(score)}%`;
    } else {
        bar.style.width = '0%';
        val.textContent = 'N/A';
    }
}

function updateLiveSensors(obs, baselineMv) {
    if (!obs) return;

    // Temperature
    const tempVal = document.getElementById('temp-val');
    if (obs.temperature_c !== null) {
        tempVal.textContent = obs.temperature_c.toFixed(1);
    }

    // Humidity
    const humVal = document.getElementById('hum-val');
    if (obs.humidity_percent !== null) {
        humVal.textContent = obs.humidity_percent.toFixed(1);
    }

    // Light
    const lightVal = document.getElementById('light-val');
    const lightLabel = document.getElementById('light-label-badge');
    const lightDesc = document.getElementById('light-class-desc');
    if (obs.light_raw !== null) {
        lightVal.textContent = obs.light_raw;
        const label = (obs.light_label || 'unknown').toUpperCase();
        lightLabel.textContent = label;
        lightLabel.className = `chip ${label === 'BRIGHT' ? 'chip-info' : label === 'DIM' ? 'chip-success' : 'chip-warning'}`;
        lightDesc.textContent = `${obs.light_label || 'normal'} room lighting`;
    }

    // MQ-135
    const mqVal = document.getElementById('mq-val');
    const mqStatus = document.getElementById('mq-status-badge');
    const mqBase = document.getElementById('mq-baseline-val');
    const mqAo = document.getElementById('mq-ao-val');
    if (obs.mq135_adc_mv !== null) {
        mqVal.textContent = obs.mq135_adc_mv;
    }
    if (baselineMv) {
        mqBase.textContent = `${Math.round(baselineMv)} mV`;
    }
    if (obs.mq135_sensor_mv !== null) {
        mqAo.textContent = `${obs.mq135_sensor_mv} mV`;
    }
    const isWarming = obs.mq135_status === 'warming_up';
    mqStatus.textContent = isWarming ? 'Warming Up' : 'Ready (Active)';
    mqStatus.className = `chip ${isWarming ? 'chip-warning' : 'chip-success'}`;

    // Sound
    const soundVal = document.getElementById('sound-val');
    const soundBadge = document.getElementById('sound-do-badge');
    const soundDesc = document.getElementById('sound-desc');
    if (obs.sound_swing !== null) {
        soundVal.textContent = obs.sound_swing;
        soundDesc.textContent = obs.sound_swing > 2000 ? 'Loud Activity' : obs.sound_swing > 500 ? 'Moderate' : 'Quiet Ambient';
    }
    if (obs.sound_do !== null) {
        soundBadge.textContent = obs.sound_do === 1 ? 'DO: Threshold Active' : 'DO: Quiet';
        soundBadge.className = `chip ${obs.sound_do === 1 ? 'chip-warning' : 'chip'}`;
    }
}

function updateRecommendations(recs) {
    const container = document.getElementById('recommendations-list');
    if (!container) return;

    if (!recs || recs.length === 0) {
        container.innerHTML = '<div class="empty-state">All environmental metrics are optimal.</div>';
        return;
    }

    container.innerHTML = recs.map(r => `
        <div class="rec-item priority-${r.priority || 'LOW'}">
            <div class="rec-title">${escapeHtml(r.title)}</div>
            <div class="rec-desc">${escapeHtml(r.explanation)}</div>
            <div class="rec-action">👉 ${escapeHtml(r.action)}</div>
        </div>
    `).join('');
}

function updateAlerts(alerts) {
    const container = document.getElementById('alerts-list');
    const countBadge = document.getElementById('active-alert-count');
    if (!container || !countBadge) return;

    countBadge.textContent = `${alerts ? alerts.length : 0} Active`;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="empty-state">No active anomalies detected. Room metrics within threshold bounds.</div>';
        return;
    }

    container.innerHTML = alerts.map(a => `
        <div class="alert-item severity-${a.severity}">
            <div class="alert-top">
                <span class="chip ${a.severity === 'CRITICAL' ? 'chip-counter' : 'chip-warning'}">${escapeHtml(a.severity)}</span>
                <span class="chip-subtle">${new Date(a.created_at).toLocaleTimeString()}</span>
            </div>
            <div style="font-weight: 600; font-size: 0.9rem; margin-top: 4px;">${escapeHtml(a.message)}</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">${escapeHtml(a.recommendation)}</div>
        </div>
    `).join('');
}

function updateForecasts(fcData) {
    renderForecastBox('fc-temp-body', fcData.temperature, '°C');
    renderForecastBox('fc-hum-body', fcData.humidity, '%');
    renderForecastBox('fc-mq-body', fcData.mq135_adc_mv, 'mV');
}

function renderForecastBox(containerId, fc, unit) {
    const el = document.getElementById(containerId);
    if (!el) return;

    if (!fc || fc.status === 'insufficient_data') {
        el.innerHTML = `<span class="chip-subtle">${fc ? fc.message : 'Awaiting data...'}</span>`;
        return;
    }

    if (fc.status === 'forecast_ready') {
        const rows = fc.projections.map(p => `
            <div class="fc-projection-row">
                <span class="fc-horizon">+${p.horizon_minutes} min:</span>
                <span class="fc-val">${p.projected_value} ${unit} <small style="color: ${p.delta > 0 ? '#fca5a5' : p.delta < 0 ? '#7dd3fc' : '#94a3b8'}">(${p.delta > 0 ? '+' : ''}${p.delta})</small></span>
            </div>
        `).join('');

        el.innerHTML = `
            ${rows}
            <div style="margin-top: 8px; font-size: 0.72rem; color: #64748b;">
                Slope: ${fc.slope_per_minute}/min | R²: ${fc.r_squared} (${fc.confidence})
            </div>
        `;
    }
}

function setDisconnectedState() {
    const pill = document.getElementById('device-pill');
    const text = document.getElementById('device-status-text');
    const banner = document.getElementById('staleness-banner');
    if (pill && text) {
        pill.className = 'status-pill disconnected';
        text.textContent = 'Server / Network Offline';
    }
    if (banner) banner.classList.remove('hidden');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
