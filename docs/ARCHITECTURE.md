# SIEIS System Architecture Specification

## 1. Executive Summary
The **Smart Indoor Environmental Intelligence System (SIEIS)** is an end-to-end edge-to-cloud architecture designed to transform indoor environmental monitoring from passive data acquisition into proactive, automated decision support.

The system comprises three primary architectural layers:
1. **Edge Acquisition Layer:** An ESP32 microcontroller acquiring physical and relative measurements from four distinct sensor subsystems, performing local validation, JSON formatting, and robust HTTP transport.
2. **Centralized Intelligence Backend:** A modular Python 3.14 / Flask service coupled with persistent SQLite time-series storage, mathematical scoring engines, rolling baseline tracking, anomaly detection, and linear forecasting.
3. **Web Decision Dashboard:** A responsive HTML5/CSS3/Vanilla JS and Chart.js interface delivering real-time telemetry, historical trend graphs, multi-parameter health scores, and actionable recommendations.

---

## 2. System Architecture Flow

```mermaid
flowchart TD
    subgraph Edge ["Edge Layer (ESP32 Node)"]
        DHT["DHT22 (GPIO 4)\nTemp & Humidity"]
        LDR["Bare LDR (GPIO 35)\n10k Voltage Divider"]
        MQ["MQ-135 (GPIO 34)\n10k:20k Divider"]
        SND["LM393 Sound (AO 32, DO 26)\n150ms Peak Swing"]
        
        ACQ["Edge Acquisition & Validation\n- Moving Average ADC\n- Peak-to-Peak Window\n- Last-Good Cache\n- Warmup Tracking"]
        JSON["JSON Serializer\nSequence No. & Uptime"]
        WIFI["Wi-Fi / HTTP Client\nTimeout & Backoff"]

        DHT --> ACQ
        LDR --> ACQ
        MQ --> ACQ
        SND --> ACQ
        ACQ --> JSON --> WIFI
    end

    subgraph Network ["Transport Layer"]
        HTTP["HTTP POST /api/sensor\nLocal Wi-Fi Hotspot (10.40.222.63:5000)"]
        WIFI --> HTTP
    end

    subgraph Backend ["Centralized Backend Layer (Python / Flask)"]
        VAL["Payload Validator\n- Range Bounds\n- Type Integrity\n- Status Flags"]
        DB[(SQLite Persistent Store\nsieis.db)]
        
        subgraph Intel ["Intelligence Engine"]
            BASE["MQ-135 Baseline Manager\n- Warmup Exclusion\n- 20% Trimmed Mean"]
            TREND["Trend Analyzer\n- Moving Averages\n- Rate of Change / min"]
            ANOM["Anomaly Detector\n- Thermal/Hygric Bounds\n- Gas Elevation Ratios\n- Cooldown & Hysteresis"]
            SCORE["Scoring Engine\n- Comfort Index\n- Environmental Health Score"]
            FC["Trend Forecaster\n- OLS Linear Extrapolation\n- Insufficient Data Safeguard"]
            DEC["Decision Engine\n- Contextual Recommendations"]
        end

        HTTP --> VAL
        VAL --> DB
        VAL --> BASE --> DB
        VAL --> TREND --> ANOM --> DB
        VAL --> SCORE --> DB
        TREND --> FC
        SCORE --> DEC
        ANOM --> DEC
    end

    subgraph UI ["Presentation Layer (Web Dashboard)"]
        DASH["Responsive HTML5 / CSS3 / Vanilla JS"]
        CHART["Chart.js Live & Historical Visualizations"]
        ALERT_UI["Active Alerts & Operational Guidance"]
        
        DB -.-> DASH
        DEC -.-> ALERT_UI
        DB -.-> CHART
    end
```

---

## 3. Telemetry Ingestion Sequence

```mermaid
sequenceDiagram
    autonumber
    participant ESP as ESP32 Sensor Node
    participant Flask as Flask API (/api/sensor)
    participant Val as Payload Validator
    participant DB as SQLite (sieis.db)
    participant Intel as Intelligence Engine
    participant UI as Browser Dashboard

    loop Every 5 Seconds
        ESP->>ESP: Acquire DHT22, LDR, MQ-135, LM393
        ESP->>ESP: Validate ranges & format JSON packet
        ESP->>Flask: HTTP POST /api/sensor
        activate Flask
        Flask->>Val: validate_incoming_packet(payload)
        alt Invalid Schema or Missing Device ID
            Val-->>Flask: ValidationError
            Flask-->>ESP: HTTP 400 Bad Request
        else Valid Telemetry
            Val-->>Flask: Sanitized Record + Flags
            Flask->>DB: insert_observation(record)
            alt Duplicate Sequence Number
                DB-->>Flask: is_duplicate = True
                Flask-->>ESP: HTTP 200 Duplicate Ignored
            else New Observation
                DB-->>Flask: observation_id
                Flask->>Intel: Update Baseline & Trends
                Flask->>Intel: Evaluate Anomalies & Alerts
                Flask->>Intel: Calculate EHS & Comfort Index
                Intel->>DB: Store Calculated Scores & Alerts
                Flask-->>ESP: HTTP 201 Created {health_score, grade}
            end
        end
        deactivate Flask
    end

    loop Every 3.5 Seconds (UI Polling)
        UI->>Flask: GET /api/stats, /api/readings, /api/alerts
        Flask->>DB: Query latest state & time-series
        DB-->>Flask: Telemetry, Scores, Alerts
        Flask-->>UI: Consolidated JSON Response
        UI->>UI: Update live cards, charts & recommendation banners
    end
```

---

## 4. Key Architectural Safeguards
1. **Idempotent Ingestion:** The database enforces uniqueness on `(device_id, sequence_number)`, ensuring network retransmissions do not distort historical time-series or rolling baselines.
2. **Warmup Quarantining:** The MQ-135 heater requires 5 minutes of thermal stabilization after power-on. Readings during this period are tagged `warming_up` and strictly excluded from baseline computation and EHS scoring.
3. **Decoupled Execution:** If network connectivity fails, the ESP32 continues local acquisition and diagnostics via USB Serial Monitor without blocking on socket calls.
4. **Transparent Degradation:** When an optional measurement channel is missing (e.g., DHT22 read timeout), the firmware supplies the last known valid reading while flagging the status as `degraded_cached`. The backend incorporates data coverage percentages into its confidence metrics.
