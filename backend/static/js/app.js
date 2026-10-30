/**
 * SIEIS (Smart Indoor Environmental Intelligence System) - Frontend Controller
 * Conforms to Master Implementation Specification Sections 5, 6, and 7.
 */

'use strict';

// Global application state
const AppState = {
    activeTab: 'overview',
    isDemoRunning: false,
    isSerialConnected: false,
    chartInstance: null,
    pollTimer: null,
};

// ==========================================================================
// Initialization
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initModals();
    initChart();

    // Initial fetch and start recurring poll loop (3 seconds)
    pollDashboardData();
    AppState.pollTimer = setInterval(pollDashboardData, 3000);

    // Initial serial ports and location load
    loadLocationConfig();
    refreshSerialPorts();

    // Wire manual weather refresh button
    document.getElementById('btn-refresh-weather')?.addEventListener('click', () => refreshOutdoorWeather(true));
});

// ==========================================================================
// Tab Switching and Keyboard Navigation (ARIA Compliant)
// ==========================================================================
function initTabs() {
    const tabOverview = document.getElementById('tab-overview');
    const tabRecs = document.getElementById('tab-recommendations');
    const panelOverview = document.getElementById('panel-overview');
    const panelRecs = document.getElementById('panel-recommendations');

    const tabs = [tabOverview, tabRecs];

    function activateTab(targetId) {
        if (targetId === 'tab-overview') {
            tabOverview.classList.add('active');
            tabOverview.setAttribute('aria-selected', 'true');
            tabOverview.setAttribute('tabindex', '0');

            tabRecs.classList.remove('active');
            tabRecs.setAttribute('aria-selected', 'false');
            tabRecs.setAttribute('tabindex', '-1');

            panelOverview.classList.add('active');
            panelOverview.classList.remove('hidden');
            panelRecs.classList.remove('active');
            panelRecs.classList.add('hidden');
            AppState.activeTab = 'overview';
        } else {
            tabRecs.classList.add('active');
            tabRecs.setAttribute('aria-selected', 'true');
            tabRecs.setAttribute('tabindex', '0');

            tabOverview.classList.remove('active');
            tabOverview.setAttribute('aria-selected', 'false');
            tabOverview.setAttribute('tabindex', '-1');

            panelRecs.classList.add('active');
            panelRecs.classList.remove('hidden');
            panelOverview.classList.remove('active');
            panelOverview.classList.add('hidden');
            AppState.activeTab = 'recommendations';
        }
    }

    tabOverview.addEventListener('click', () => activateTab('tab-overview'));
    tabRecs.addEventListener('click', () => activateTab('tab-recommendations'));

    // Keyboard navigation (ArrowLeft, ArrowRight, Home, End)
    tabs.forEach((tab, index) => {
        tab.addEventListener('keydown', (e) => {
            let nextIndex = index;
            if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                nextIndex = (index + 1) % tabs.length;
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                nextIndex = (index - 1 + tabs.length) % tabs.length;
            } else if (e.key === 'Home') {
                nextIndex = 0;
            } else if (e.key === 'End') {
                nextIndex = tabs.length - 1;
            } else {
                return;
            }
            e.preventDefault();
            tabs[nextIndex].focus();
            activateTab(tabs[nextIndex].id);
        });
    });
}

// ==========================================================================
// Modals Management
// ==========================================================================
function initModals() {
    // Open modal buttons
    document.getElementById('btn-location-modal')?.addEventListener('click', openLocationModal);
    document.getElementById('btn-tools-modal')?.addEventListener('click', openToolsModal);
    document.getElementById('btn-open-charts-modal')?.addEventListener('click', openChartsModal);

    // Close on backdrop click or ESC key
    document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                backdrop.classList.add('hidden');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-backdrop').forEach((b) => b.classList.add('hidden'));
        }
    });

    document.getElementById('history-limit-select')?.addEventListener('change', () => {
        updateChartHistory();
    });
}

function openLocationModal() {
    loadLocationConfig();
    document.getElementById('modal-location')?.classList.remove('hidden');
}

function closeLocationModal() {
    document.getElementById('modal-location')?.classList.add('hidden');
}

function openToolsModal() {
    refreshSerialPorts();
    document.getElementById('modal-tools')?.classList.remove('hidden');
}

function closeToolsModal() {
    document.getElementById('modal-tools')?.classList.add('hidden');
}

function openChartsModal() {
    document.getElementById('modal-charts')?.classList.remove('hidden');
    updateChartHistory();
}

function closeChartsModal() {
    document.getElementById('modal-charts')?.classList.add('hidden');
}

// ==========================================================================
// Location Configuration
// ==========================================================================
async function loadLocationConfig() {
    try {
        const res = await fetch('/api/config/location');
        if (res.ok) {
            const data = await res.json();
            const labelEl = document.getElementById('header-location-name');
            if (labelEl && data.location_label) {
                labelEl.textContent = data.location_label;
            }
            const inLabel = document.getElementById('input-loc-label');
            const inLat = document.getElementById('input-latitude');
            const inLon = document.getElementById('input-longitude');
            if (inLabel) inLabel.value = data.location_label || '';
            if (inLat) inLat.value = data.latitude || '';
            if (inLon) inLon.value = data.longitude || '';
        }
    } catch (e) {
        console.debug('Failed loading location:', e);
    }
}

async function saveLocationSettings(e) {
    e.preventDefault();
    const lat = parseFloat(document.getElementById('input-latitude')?.value);
    const lon = parseFloat(document.getElementById('input-longitude')?.value);
    const label = document.getElementById('input-loc-label')?.value;

    try {
        const res = await fetch('/api/config/location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lon, location_label: label }),
        });
        if (res.ok) {
            closeLocationModal();
            loadLocationConfig();
            pollDashboardData();
        }
    } catch (err) {
        alert('Failed updating location: ' + err);
    }
}

// ==========================================================================
// Simulation & USB Serial Controls
// ==========================================================================
async function refreshSerialPorts() {
    try {
        const res = await fetch('/api/serial/ports');
        if (res.ok) {
            const data = await res.json();
            const select = document.getElementById('serial-port-select');
            if (select && data.ports && data.ports.length > 0) {
                select.innerHTML = data.ports.map((p) => `<option value="${p}" ${p === 'COM4' ? 'selected' : ''}>${p}</option>`).join('');
            }
        }
    } catch (e) {
        console.debug('Serial ports error:', e);
    }
}

async function toggleSerialBridge() {
    const btn = document.getElementById('btn-toggle-serial');
    const port = document.getElementById('serial-port-select')?.value || 'COM4';

    if (!AppState.isSerialConnected) {
        const res = await fetch('/api/serial/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port }),
        });
        if (res.ok) {
            AppState.isSerialConnected = true;
            if (btn) btn.textContent = `Disconnect (${port})`;
        }
    } else {
        const res = await fetch('/api/serial/disconnect', { method: 'POST' });
        if (res.ok) {
            AppState.isSerialConnected = false;
            if (btn) btn.textContent = `Connect USB (${port})`;
        }
    }
    pollDashboardData();
}

async function resetEsp32Hardware() {
    const btn = document.getElementById('btn-reset-esp32');
    if (btn) btn.disabled = true;
    try {
        const res = await fetch('/api/serial/reset', { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            console.log('Hardware reset pulse sent to ESP32 on ' + (data.port || 'COM4'));
        }
    } catch (e) {
        console.error('Reset command failed:', e);
    } finally {
        if (btn) btn.disabled = false;
        pollDashboardData();
    }
}

async function reconnectSerialBridge() {
    const btn = document.getElementById('btn-reconnect-serial');
    const port = document.getElementById('serial-port-select')?.value || 'COM4';
    if (btn) btn.disabled = true;
    try {
        const res = await fetch('/api/serial/reconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port }),
        });
        if (res.ok) {
            AppState.isSerialConnected = true;
        }
    } catch (e) {
        console.error('Reconnect failed:', e);
    } finally {
        if (btn) btn.disabled = false;
        pollDashboardData();
    }
}

async function toggleDemoStream() {
    const btn = document.getElementById('btn-toggle-demo');
    if (!AppState.isDemoRunning) {
        const res = await fetch('/api/demo/start', { method: 'POST' });
        if (res.ok) {
            AppState.isDemoRunning = true;
            if (btn) {
                btn.textContent = '⏹️ Pause Simulation';
                btn.className = 'btn btn-danger';
            }
        }
    } else {
        const res = await fetch('/api/demo/stop', { method: 'POST' });
        if (res.ok) {
            AppState.isDemoRunning = false;
            if (btn) {
                btn.textContent = '▶️ Start Simulation';
                btn.className = 'btn btn-primary';
            }
        }
    }
    pollDashboardData();
}

async function triggerDemoEvent(eventMode) {
    await fetch('/api/demo/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: eventMode }),
    });
    pollDashboardData();
}

// ==========================================================================
// Weather Refresh Controller (Manual & Periodic)
// ==========================================================================
let isWeatherRefreshing = false;
async function refreshOutdoorWeather(isManual = false) {
    if (isWeatherRefreshing) return;
    isWeatherRefreshing = true;
    const btn = document.getElementById('btn-refresh-weather');
    if (btn) {
        btn.classList.add('spinning');
        btn.disabled = true;
        const lbl = btn.querySelector('.refresh-label');
        if (lbl) lbl.textContent = 'Fetching...';
    }

    try {
        const cacheBuster = `_t=${Date.now()}`;
        const forceParam = isManual ? 'refresh=true&' : '';
        const res = await fetch(`/api/outdoor?${forceParam}${cacheBuster}`, {
            cache: 'no-store',
            headers: { 'Pragma': 'no-cache', 'Cache-Control': 'no-cache' },
        });
        if (res.ok) {
            const outData = await res.json();
            updateOutdoorCard(outData);
            const [comp, recs, diag] = await Promise.all([
                fetch(`/api/comparison?${cacheBuster}`, { cache: 'no-store' }).then((r) => r.json()).catch(() => null),
                fetch(`/api/recommendations?${cacheBuster}`, { cache: 'no-store' }).then((r) => r.json()).catch(() => null),
                fetch(`/api/diagnostics?${cacheBuster}`, { cache: 'no-store' }).then((r) => r.json()).catch(() => null),
            ]);
            if (comp) updateComparisonCard(comp);
            if (recs) updateRecommendations(recs);
            if (diag) updateDiagnosticsMatrix(diag);
        }
    } catch (err) {
        console.error('Failed refreshing outdoor weather:', err);
    } finally {
        isWeatherRefreshing = false;
        if (btn) {
            btn.classList.remove('spinning');
            btn.disabled = false;
            const lbl = btn.querySelector('.refresh-label');
            if (lbl) lbl.textContent = 'Refresh';
        }
    }
}

// ==========================================================================
// Core Polling & Data Dispatcher
// ==========================================================================
async function pollDashboardData() {
    try {
        const noCache = { cache: 'no-store' };
        const [
            statsRes,
            rciRes,
            estRes,
            outRes,
            compRes,
            recsRes,
            diagRes,
            fcRes,
        ] = await Promise.all([
            fetch('/api/stats', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/comfort-index', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/indoor-estimates', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/outdoor', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/comparison', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/recommendations', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/diagnostics', noCache).then((r) => r.json()).catch(() => null),
            fetch('/api/forecast', noCache).then((r) => r.json()).catch(() => null),
        ]);

        if (statsRes) updateHeaderStatuses(statsRes);
        if (rciRes) updateRCIHero(rciRes);
        if (statsRes?.latest_observation) updateSensorTiles(statsRes.latest_observation, statsRes);
        if (outRes) updateOutdoorCard(outRes);
        if (compRes) updateComparisonCard(compRes);
        if (estRes) updateEstimatesCard(estRes);
        if (fcRes) updateForecasts(fcRes);
        if (recsRes) updateRecommendations(recsRes);
        if (diagRes) updateDiagnosticsMatrix(diagRes);

    } catch (err) {
        console.error('Polling error:', err);
    }
}

// ==========================================================================
// UI Renderers
// ==========================================================================
function updateHeaderStatuses(stats) {
    const subs = stats.subsystem_statuses || {};
    const freshness = stats.freshness || {};

    // USB Bridge pill
    const pillUsb = document.getElementById('pill-usb');
    if (pillUsb) {
        const usbStatus = subs.usb_bridge_status || 'disconnected';
        const isLive = usbStatus === 'connected';
        const isSilent = usbStatus === 'connected_silent';
        AppState.isSerialConnected = isLive || isSilent;

        if (isLive) {
            pillUsb.className = 'status-pill status-connected';
            pillUsb.querySelector('.pill-text').textContent = 'USB: COM4 (Live)';
            pillUsb.title = 'ESP32 hardware serial telemetry is actively streaming live packets.';
        } else if (isSilent) {
            pillUsb.className = 'status-pill status-cached';
            pillUsb.querySelector('.pill-text').textContent = 'USB: COM4 (Silent)';
            pillUsb.title = 'COM4 is open, but no sensor telemetry packets received in >15s. Press EN/Reset on ESP32 or start simulation.';
        } else {
            pillUsb.className = 'status-pill status-disconnected';
            pillUsb.querySelector('.pill-text').textContent = 'USB: Disconnected';
            pillUsb.title = 'USB serial bridge disconnected.';
        }
    }

    // Wi-Fi HTTP pill
    const pillWifi = document.getElementById('pill-wifi');
    if (pillWifi) {
        const isWifi = subs.wifi_http_telemetry_status === 'active';
        pillWifi.className = `status-pill ${isWifi ? 'status-active' : 'status-cached'}`;
        pillWifi.querySelector('.pill-text').textContent = isWifi ? 'Wi-Fi: Active' : 'Wi-Fi: Standby';
    }

    // Outdoor API pill
    const pillOut = document.getElementById('pill-outdoor');
    if (pillOut) {
        const outStatus = subs.outdoor_api_status || 'offline';
        const cls = outStatus === 'live' ? 'status-live' : outStatus === 'cached' || outStatus === 'stale_cached' ? 'status-cached' : 'status-offline';
        pillOut.className = `status-pill ${cls}`;
        pillOut.querySelector('.pill-text').textContent = `Outdoor: ${outStatus.toUpperCase()}`;
    }

    // Telemetry Age
    const ageEl = document.getElementById('telemetry-age-text');
    if (ageEl) {
        if (freshness.seconds_since_last !== null && freshness.seconds_since_last !== undefined) {
            const sec = freshness.seconds_since_last;
            ageEl.textContent = freshness.is_stale ? `Stale: ${sec}s` : `Live: ${sec}s`;
            const agePill = document.getElementById('pill-age');
            if (agePill) {
                agePill.style.color = freshness.is_stale ? '#fbbf24' : '#38bdf8';
                agePill.style.borderColor = freshness.is_stale ? 'rgba(245, 158, 11, 0.4)' : 'rgba(56, 189, 248, 0.25)';
            }
        } else {
            ageEl.textContent = 'Awaiting data';
        }
    }
}

function updateRCIHero(rci) {
    const scoreNum = document.getElementById('rci-score-number');
    const badge = document.getElementById('rci-status-badge');
    const coverage = document.getElementById('rci-coverage-badge');
    const confidence = document.getElementById('rci-confidence-val');
    const progressCircle = document.getElementById('rci-dial-progress');
    const posFact = document.getElementById('rci-positive-factor');
    const negFact = document.getElementById('rci-negative-factor');
    const staleTag = document.getElementById('rci-stale-tag');

    const score = rci.score;
    const circumference = 263.89; // 2 * pi * 42

    if (score !== null && score !== undefined) {
        if (scoreNum) scoreNum.textContent = Math.round(score);
        const offset = circumference * (1 - score / 100);
        if (progressCircle) {
            progressCircle.style.strokeDashoffset = offset;
            if (score >= 80) progressCircle.style.stroke = '#10b981';
            else if (score >= 50) progressCircle.style.stroke = '#f59e0b';
            else progressCircle.style.stroke = '#ef4444';
        }

        if (badge) {
            badge.textContent = rci.status || 'Active';
            badge.className = `status-badge ${rci.color_band === 'green' ? 'status-green' : rci.color_band === 'yellow' ? 'status-yellow' : 'status-red'}`;
        }
    } else {
        if (scoreNum) scoreNum.textContent = '--';
        if (progressCircle) {
            progressCircle.style.strokeDashoffset = circumference;
            progressCircle.style.stroke = '#64748b';
        }
        if (badge) {
            badge.textContent = 'INDETERMINATE';
            badge.className = 'status-badge status-gray';
        }
    }

    if (coverage) coverage.textContent = `${rci.data_coverage_percent || 0}% Coverage`;
    if (confidence) confidence.textContent = rci.confidence_level || 'Moderate';

    if (staleTag) {
        if (rci.is_stale) {
            staleTag.className = 'stale-warn-tag';
            staleTag.innerHTML = `⚠️ Telemetry Stale &bull; <button type="button" class="stale-action-btn" onclick="toggleDemoStream()" title="Start live simulated telemetry stream">▶ Resume Live Data</button>`;
        } else {
            staleTag.className = 'stale-warn-tag hidden';
            staleTag.textContent = '⚠️ Stale Telemetry';
        }
    }

    if (posFact) {
        const pos = rci.main_positive_contributors || [];
        posFact.textContent = pos.length > 0 ? pos.slice(0, 2).join(', ') : 'All parameters optimal';
    }
    if (negFact) {
        const neg = rci.main_negative_contributors || [];
        negFact.textContent = neg.length > 0 ? neg.slice(0, 2).join(', ') : 'None';
    }
}

function updateSensorTiles(obs, stats) {
    const flashElement = (el, newVal) => {
        if (!el) return;
        if (el.textContent !== newVal) {
            el.textContent = newVal;
            el.classList.add('flash-update');
            setTimeout(() => el.classList.remove('flash-update'), 600);
        }
    };

    // 1. Temperature
    const tVal = document.getElementById('tile-temp-val');
    const tChip = document.getElementById('tile-temp-status');
    const tempText = obs.temperature_c !== null ? obs.temperature_c.toFixed(1) : '--';
    flashElement(tVal, tempText);

    if (tChip && obs.temperature_c !== null) {
        const t = obs.temperature_c;
        if (t >= 21.0 && t <= 24.0) {
            tChip.textContent = 'Optimal (21-24°C)';
            tChip.className = 'tile-chip chip-bright';
        } else if (t >= 18.0 && t <= 27.0) {
            tChip.textContent = 'Acceptable';
            tChip.className = 'tile-chip chip-dim';
        } else {
            tChip.textContent = t > 27.0 ? 'Overheating' : 'Cold';
            tChip.className = 'tile-chip chip-dark';
        }
    }

    // 2. Humidity
    const hVal = document.getElementById('tile-rh-val');
    const hChip = document.getElementById('tile-rh-status');
    const humText = obs.humidity_percent !== null ? obs.humidity_percent.toFixed(1) : '--';
    flashElement(hVal, humText);

    if (hChip && obs.humidity_percent !== null) {
        const h = obs.humidity_percent;
        if (h >= 40.0 && h <= 60.0) {
            hChip.textContent = 'Optimal (40-60%)';
            hChip.className = 'tile-chip chip-bright';
        } else if (h > 60.0) {
            hChip.textContent = 'High Moisture';
            hChip.className = 'tile-chip chip-dim';
        } else {
            hChip.textContent = 'Dry Air';
            hChip.className = 'tile-chip chip-dim';
        }
    }

    // 3. LDR Brightness
    const ldrVal = document.getElementById('tile-ldr-val');
    const ldrBadge = document.getElementById('tile-ldr-badge');
    const ldrText = obs.light_raw !== null ? String(obs.light_raw) : '--';
    flashElement(ldrVal, ldrText);

    if (ldrBadge && obs.light_raw !== null) {
        const raw = obs.light_raw;
        if (raw >= 1700) {
            ldrBadge.textContent = 'Bright';
            ldrBadge.className = 'tile-chip chip-bright';
        } else if (raw >= 250) {
            ldrBadge.textContent = 'Dim';
            ldrBadge.className = 'tile-chip chip-dim';
        } else {
            ldrBadge.textContent = 'Dark';
            ldrBadge.className = 'tile-chip chip-dark';
        }
    }

    // 4. MQ-135 Gas
    const mqVal = document.getElementById('tile-mq-val');
    const mqBadge = document.getElementById('tile-mq-badge');
    const mqRatio = document.getElementById('tile-mq-ratio');
    const mv = obs.mq135_sensor_mv || obs.mq135_adc_mv;
    const mqText = mv !== null ? String(Math.round(mv)) : '--';
    flashElement(mqVal, mqText);

    const base = stats.mq135_baseline_mv;
    if (mqRatio) {
        if (mv && base && base > 0) {
            const r = (mv / base).toFixed(2);
            mqRatio.textContent = `${r}x`;
            mqRatio.className = r > 1.25 ? 'tile-ratio-tag chip-dark' : 'tile-ratio-tag';
        } else {
            mqRatio.textContent = '1.00x';
        }
    }

    if (mqBadge) {
        const status = obs.mq135_status || 'ready';
        if (status === 'warming_up') {
            mqBadge.textContent = 'Heater Warm-up';
            mqBadge.className = 'tile-chip chip-dim';
        } else {
            mqBadge.textContent = 'Baseline Ready';
            mqBadge.className = 'tile-chip chip-bright';
        }
    }

    // 5. Sound
    const sndVal = document.getElementById('tile-sound-val');
    const sndTrigger = document.getElementById('tile-sound-trigger');
    const sndText = obs.sound_swing !== null ? String(obs.sound_swing) : '--';
    flashElement(sndVal, sndText);

    if (sndTrigger) {
        if (obs.sound_do === 1 || (obs.sound_swing && obs.sound_swing >= 1200)) {
            sndTrigger.textContent = 'Trigger Active';
            sndTrigger.className = 'tile-chip chip-dark';
        } else {
            sndTrigger.textContent = 'Quiet';
            sndTrigger.className = 'tile-chip chip-dim';
        }
    }
}

function updateOutdoorCard(out) {
    const aqiVal = document.getElementById('outdoor-aqi-val');
    const aqiCat = document.getElementById('outdoor-aqi-category');
    const tempVal = document.getElementById('outdoor-temp-val');
    const rhVal = document.getElementById('outdoor-rh-val');
    const freshBadge = document.getElementById('outdoor-freshness-badge');
    const locLabel = document.getElementById('outdoor-location-label');
    const srcTag = document.getElementById('outdoor-source-tag');
    const obsTimeEl = document.getElementById('outdoor-observed-time');
    const fetchTimeEl = document.getElementById('outdoor-fetched-time');
    const attrText = document.getElementById('outdoor-attribution-text');

    if (aqiVal) aqiVal.textContent = out.aqi !== null && out.aqi !== undefined ? Math.round(out.aqi) : '--';
    if (aqiCat) aqiCat.textContent = out.aqi_category || 'Unknown';
    if (tempVal) tempVal.textContent = out.temperature_c !== null && out.temperature_c !== undefined ? `${out.temperature_c.toFixed(1)} °C` : '-- °C';
    if (rhVal) rhVal.textContent = out.relative_humidity_pct !== null && out.relative_humidity_pct !== undefined ? `${Math.round(out.relative_humidity_pct)} %` : '-- %';
    if (locLabel && out.location_label) locLabel.textContent = out.location_label;
    if (attrText && out.attribution) attrText.textContent = out.attribution;

    // Epistemic Source Tag
    if (srcTag) {
        const provider = out.provider || 'Outdoor';
        const srcType = out.source_type === 'station_observation'
            ? 'Station Observation'
            : out.source_type === 'numerical_model_estimate'
                ? 'Model Nowcast'
                : 'Atmospheric API';
        srcTag.textContent = `${provider} (${srcType})`;
    }

    // Freshness Badge (Live / Cached / Stale / Offline)
    if (freshBadge) {
        const st = out.freshness_status || 'offline';
        if (st === 'live') {
            freshBadge.textContent = 'LIVE';
            freshBadge.className = 'chip chip-live';
        } else if (st === 'cached') {
            freshBadge.textContent = 'CACHED';
            freshBadge.className = 'chip chip-cached';
        } else if (st === 'stale_observation' || st === 'stale_cached' || out.is_stale) {
            freshBadge.textContent = 'STALE';
            freshBadge.className = 'chip chip-stale';
        } else if (st === 'offline') {
            freshBadge.textContent = 'OFFLINE';
            freshBadge.className = 'chip chip-stale';
        } else {
            freshBadge.textContent = st.replace('_', ' ').toUpperCase();
            freshBadge.className = 'chip chip-cached';
        }
    }

    // Underlying Provider Observation Time & Calculated Age
    if (obsTimeEl) {
        if (out.observed_at) {
            let ageText = '';
            if (out.age_seconds !== null && out.age_seconds !== undefined) {
                const m = Math.floor(out.age_seconds / 60);
                const s = out.age_seconds % 60;
                ageText = m > 0 ? `${m}m ${s}s ago` : `${s}s ago`;
            }
            let timeDisplay = out.observed_at;
            if (timeDisplay.includes('T')) {
                const parts = timeDisplay.split('T')[1];
                timeDisplay = parts.substring(0, 5);
            } else if (timeDisplay.includes(' ')) {
                timeDisplay = timeDisplay.split(' ')[1]?.substring(0, 5) || timeDisplay;
            }
            obsTimeEl.textContent = `Obs: ${timeDisplay} (${ageText || 'current'})`;
        } else {
            obsTimeEl.textContent = 'Obs: Unavailable';
        }
    }

    // Backend Retrieval / Fetch Time
    if (fetchTimeEl) {
        if (out.fetched_at) {
            try {
                const d = new Date(out.fetched_at);
                const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                fetchTimeEl.textContent = `Fetched: ${timeStr}`;
            } catch (e) {
                fetchTimeEl.textContent = `Fetched: ${out.fetched_at.substring(11, 19)}`;
            }
        } else {
            fetchTimeEl.textContent = 'Fetched: --';
        }
    }
}

function updateComparisonCard(comp) {
    const dTemp = document.getElementById('delta-temp-val');
    const dTempNote = document.getElementById('delta-temp-note');
    const dRh = document.getElementById('delta-rh-val');
    const dRhNote = document.getElementById('delta-rh-note');
    const dpVal = document.getElementById('dew-point-val');
    const ahVal = document.getElementById('abs-humidity-val');
    const deltaAh = document.getElementById('delta-ah-val');
    const ventBadge = document.getElementById('vent-rating-badge');
    const ventText = document.getElementById('vent-explanation-text');
    const tileDew = document.getElementById('tile-dewpoint-sub');

    const t = comp.temperature || {};
    const h = comp.humidity || {};
    const psych = h.psychrometrics || {};
    const vent = comp.ventilation_assessment || {};

    if (dTemp) {
        const delta = t.delta_c;
        dTemp.textContent = delta !== null && delta !== undefined ? `${delta > 0 ? '+' : ''}${delta.toFixed(1)} °C` : '-- °C';
    }
    if (dTempNote) {
        dTempNote.textContent = t.direction === 'outdoor_cooler' ? 'Outdoors is Cooler' : t.direction === 'outdoor_warmer' ? 'Outdoors is Hotter' : 'Equilibrium';
    }

    if (dRh) {
        const deltaRh = h.delta_rh_pp;
        dRh.textContent = deltaRh !== null && deltaRh !== undefined ? `${deltaRh > 0 ? '+' : ''}${deltaRh.toFixed(1)} pp` : '-- pp';
    }

    if (dpVal) {
        dpVal.textContent = psych.indoor_dew_point_c !== null ? `${psych.indoor_dew_point_c.toFixed(1)} °C` : '-- °C';
        if (tileDew && psych.indoor_dew_point_c !== null) {
            tileDew.textContent = `Dew Point: ${psych.indoor_dew_point_c.toFixed(1)} °C`;
        }
    }

    if (ahVal) {
        ahVal.textContent = psych.indoor_absolute_humidity_gm3 !== null ? `${psych.indoor_absolute_humidity_gm3.toFixed(1)} g/m³` : '-- g/m³';
    }
    if (deltaAh && psych.delta_absolute_humidity_gm3 !== null) {
        deltaAh.textContent = `Δ AH: ${psych.delta_absolute_humidity_gm3.toFixed(1)} g/m³`;
    }

    if (ventBadge) {
        const rating = vent.rating || 'indeterminate';
        ventBadge.textContent = rating.toUpperCase();
        ventBadge.className = `rating-badge ${rating === 'favourable' ? 'rating-favourable' : rating === 'unfavourable' ? 'rating-unfavourable' : rating === 'mixed' ? 'rating-mixed' : 'rating-indeterminate'}`;
    }

    if (ventText) {
        ventText.textContent = vent.explanation || 'Calculating ventilation favourability...';
    }
}

function updateEstimatesCard(est) {
    const pm25 = est.pm25 || {};
    const co2 = est.co2 || {};

    const pmVal = document.getElementById('est-pm25-val');
    const pmStatus = document.getElementById('pm25-cal-status');
    const co2Val = document.getElementById('est-co2-val');
    const co2Status = document.getElementById('co2-cal-status');

    if (pmVal) pmVal.textContent = pm25.value !== null && pm25.value !== undefined ? pm25.value.toFixed(1) : '--';
    if (pmStatus) pmStatus.textContent = pm25.calibration_status ? pm25.calibration_status.replace('_', ' ') : 'Proxy';

    if (co2Val) co2Val.textContent = co2.value !== null && co2.value !== undefined ? co2.value : '--';
    if (co2Status) co2Status.textContent = co2.calibration_status ? co2.calibration_status.replace('_', ' ') : 'Proxy';
}

function updateForecasts(fc) {
    const t5 = document.getElementById('fc-temp-5');
    const t15 = document.getElementById('fc-temp-15');
    const h15 = document.getElementById('fc-rh-15');
    const gTrend = document.getElementById('fc-gas-trend');

    const tempFc = fc.temperature || {};
    const humFc = fc.humidity || {};
    const gasFc = fc.gas || {};

    if (t5) t5.textContent = tempFc.temp_plus_5m !== undefined ? `${tempFc.temp_plus_5m.toFixed(1)} °C` : '-- °C';
    if (t15) t15.textContent = tempFc.temp_plus_15m !== undefined ? `${tempFc.temp_plus_15m.toFixed(1)} °C` : '-- °C';
    if (h15) h15.textContent = humFc.humidity_plus_15m !== undefined ? `${humFc.humidity_plus_15m.toFixed(1)} %` : '-- %';
    if (gTrend) gTrend.textContent = gasFc.trend || 'Stable';
}

function updateRecommendations(recsData) {
    const recs = recsData.recommendations || [];
    const count = recs.length;

    // Badge on tab
    const badge = document.getElementById('badge-rec-count');
    if (badge) {
        badge.textContent = count;
        badge.className = count > 0 ? 'badge-count' : 'badge-count hidden';
    }

    const countLabel = document.getElementById('recs-count-label');
    if (countLabel) countLabel.textContent = `${count} Active Items`;

    // Hero Top Issue
    const hero = recsData.highest_priority || (recs.length > 0 ? recs[0] : null);
    const heroTitle = document.getElementById('hero-rec-title');
    const heroWrong = document.getElementById('hero-rec-wrong');
    const heroTarget = document.getElementById('hero-rec-target');
    const heroAction = document.getElementById('hero-rec-action');
    const heroSev = document.getElementById('hero-rec-severity');
    const heroEvidence = document.getElementById('hero-rec-evidence');

    if (hero) {
        if (heroTitle) heroTitle.textContent = hero.title;
        if (heroWrong) heroWrong.textContent = hero.what_is_wrong;
        if (heroTarget) heroTarget.textContent = hero.target_metric;
        if (heroAction) heroAction.textContent = hero.recommended_action;
        if (heroSev) {
            heroSev.textContent = (hero.severity || 'ADVISORY').toUpperCase();
            heroSev.className = `chip chip-sev ${hero.severity === 'critical' ? 'chip-dark' : 'chip-dim'}`;
        }
        if (heroEvidence) {
            heroEvidence.textContent = `${hero.current_value_summary || ''} — ${hero.explanation || ''}`;
        }
    } else {
        if (heroTitle) heroTitle.textContent = 'All Environmental Parameters Nominal';
        if (heroWrong) heroWrong.textContent = 'Indoor temperature, humidity, and gas signals comply with target comfort bounds.';
        if (heroTarget) heroTarget.textContent = 'Room Comfort Index (Target: >= 80)';
        if (heroAction) heroAction.textContent = 'No active intervention required. Maintain current environmental settings.';
        if (heroSev) heroSev.textContent = 'NORMAL';
        if (heroEvidence) heroEvidence.textContent = 'Indoor: Nominal | Outdoor: Clean';
    }

    // Secondary list
    const list = document.getElementById('secondary-recs-list');
    if (list) {
        const secondary = recs.slice(1);
        if (secondary.length === 0) {
            list.innerHTML = '<div class="empty-recs-placeholder">No secondary alerts. All sensor systems operating within standard bounds.</div>';
        } else {
            list.innerHTML = secondary.map((r) => `
                <div class="rec-item-compact sev-${r.severity || 'info'}">
                    <div class="rec-item-top">
                        <span class="rec-item-title">${r.title}</span>
                        <span class="chip">${(r.severity || 'info').toUpperCase()}</span>
                    </div>
                    <div class="rec-item-action">${r.recommended_action}</div>
                </div>
            `).join('');
        }
    }
}

function updateDiagnosticsMatrix(diag) {
    const subs = diag.subsystems || {};

    const mapping = {
        usb_bridge: { cell: 'diag-cell-usb', sub: 'diag-sub-usb' },
        wifi_telemetry: { cell: 'diag-cell-wifi', sub: 'diag-sub-wifi' },
        backend_server: { cell: 'diag-cell-backend', sub: 'diag-sub-backend' },
        sqlite_database: { cell: 'diag-cell-database', sub: 'diag-sub-database' },
        dht22_sensor: { cell: 'diag-cell-dht22', sub: 'diag-sub-dht22' },
        mq135_sensor: { cell: 'diag-cell-mq135', sub: 'diag-sub-mq135' },
        experimental_estimators: { cell: 'diag-cell-estimators', sub: 'diag-sub-estimators' },
        outdoor_api: { cell: 'diag-cell-outdoor', sub: 'diag-sub-outdoor' },
        rci_coverage: { cell: 'diag-cell-rci', sub: 'diag-sub-rci' },
    };

    for (const [key, map] of Object.entries(mapping)) {
        const info = subs[key];
        if (!info) continue;

        const cellEl = document.getElementById(map.cell);
        const subEl = document.getElementById(map.sub);

        if (subEl) {
            subEl.textContent = info.detail || info.status.toUpperCase();
        }

        if (cellEl) {
            const dot = cellEl.querySelector('.diag-dot');
            if (dot) {
                const st = info.status;
                if (st === 'healthy' || st === 'connected' || st === 'active' || st === 'complete' || st === 'live') {
                    dot.className = 'diag-dot dot-green';
                } else if (st === 'warming_up' || st === 'partial' || st === 'cached' || st === 'uncalibrated_heuristic' || st === 'degraded') {
                    dot.className = 'diag-dot dot-amber';
                } else if (st === 'error' || st === 'insufficient' || st === 'offline' || st === 'disconnected') {
                    dot.className = 'diag-dot dot-red';
                } else {
                    dot.className = 'diag-dot dot-gray';
                }
            }
        }
    }
}

// ==========================================================================
// Chart.js Multi-Sensor Trend Visualizer
// ==========================================================================
function initChart() {
    const canvas = document.getElementById('multiSensorChart');
    if (!canvas || !window.Chart) return;

    const ctx = canvas.getContext('2d');
    AppState.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    yAxisID: 'yTemp',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 1,
                },
                {
                    label: 'Humidity (%)',
                    data: [],
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    yAxisID: 'yHum',
                    tension: 0.3,
                    borderWidth: 2,
                    pointRadius: 1,
                },
                {
                    label: 'MQ-135 Gas (mV)',
                    data: [],
                    borderColor: '#f59e0b',
                    backgroundColor: 'transparent',
                    yAxisID: 'yGas',
                    tension: 0.3,
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                    pointRadius: 1,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } },
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#64748b', maxTicksLimit: 8 },
                },
                yTemp: {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#38bdf8' },
                    title: { display: true, text: 'Temp (°C)', color: '#38bdf8' },
                },
                yHum: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#10b981' },
                    title: { display: true, text: 'Humidity (%)', color: '#10b981' },
                },
                yGas: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#f59e0b' },
                    title: { display: false },
                },
            },
        },
    });
}

async function updateChartHistory() {
    if (!AppState.chartInstance) return;
    const limit = document.getElementById('history-limit-select')?.value || 60;
    try {
        const res = await fetch(`/api/readings?limit=${limit}`);
        if (!res.ok) return;
        const data = await res.json();
        const readings = data.readings || [];
        // Sort chronologically ascending
        readings.sort((a, b) => new Date(a.received_at) - new Date(b.received_at));

        const labels = readings.map((r) => {
            const d = new Date(r.received_at);
            return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
        });

        const temps = readings.map((r) => r.temperature_c);
        const hums = readings.map((r) => r.humidity_percent);
        const gases = readings.map((r) => r.mq135_sensor_mv || r.mq135_adc_mv);

        AppState.chartInstance.data.labels = labels;
        AppState.chartInstance.data.datasets[0].data = temps;
        AppState.chartInstance.data.datasets[1].data = hums;
        AppState.chartInstance.data.datasets[2].data = gases;
        AppState.chartInstance.update();
    } catch (e) {
        console.debug('Chart history update failed:', e);
    }
}
