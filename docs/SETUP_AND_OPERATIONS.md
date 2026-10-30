# SIEIS Setup & Operations Guide (Windows)

This guide walks you through setting up, configuring, running, and demonstrating the complete **Smart Indoor Environmental Intelligence System (SIEIS)** on Windows.

---

## 1. Prerequisites Check
Ensure your laptop has:
1. **Python 3.10+** (Detected: Python 3.14 on your machine).
2. **Arduino IDE 2.x** or bundled `arduino-cli` (Located in Downloads/Arduino IDE).
3. **ESP32 Board** connected via Micro-USB (Detected on `COM4` with CP210x driver).
4. **Phone Hotspot or Local Wi-Fi** shared between your laptop and the ESP32.

---

## 2. Step-by-Step Operating Sequence

### Step 1: Open PowerShell in the Project Directory
Open PowerShell and verify you are in the workspace root:
```powershell
cd c:\Users\insan\OneDrive\Desktop\SIEIS
```

### Step 2: Verify Python Environment & Dependencies
The Python virtual environment `.venv` has already been created and prepared. To verify packages:
```powershell
.\.venv\Scripts\python.exe -m pip list
```
*(Expected: `flask`, `pytest`, `pytest-mock` installed).*

If you ever need to re-install dependencies:
```powershell
.\.venv\Scripts\pip.exe install -r backend\requirements.txt
```

### Step 3: Check Your Active Wi-Fi / Hotspot IPv4 Address
To find your laptop's current IP address on your phone hotspot:
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -match "WiFi" } | Select-Object InterfaceAlias, IPAddress
```
*Example Output:*
```
InterfaceAlias IPAddress
-------------- ---------
WiFi           10.40.222.63
```
*(If the IP address changed when reconnecting your hotspot, take note of the new IP).*

### Step 4: Configure the ESP32 Firmware
1. Copy the configuration template:
   ```powershell
   Copy-Item firmware\SIEIS_ESP32\config.example.h firmware\SIEIS_ESP32\config.h
   ```
2. Open `firmware\SIEIS_ESP32\config.h` in any text editor.
3. Update `WIFI_SSID` and `WIFI_PASSWORD` with your actual phone hotspot credentials.
4. Ensure `BACKEND_SERVER_URL` matches your laptop's hotspot IP from Step 3:
   ```c
   #define WIFI_SSID             "MyHotspot"
   #define WIFI_PASSWORD         "MyPassword123"
   #define BACKEND_SERVER_URL    "http://10.40.222.63:5000/api/sensor"
   ```

### Step 5: Flash the ESP32 Node
You can upload either using Arduino IDE or the command line.

#### Option A: Using Arduino IDE
1. Launch Arduino IDE.
2. Open `firmware\SIEIS_ESP32\SIEIS_ESP32.ino`.
3. Select **Tools -> Board -> esp32 -> ESP32 Dev Module**.
4. Select **Tools -> Port -> COM4**.
5. Click **Upload** (Ctrl + U).
6. Open **Tools -> Serial Monitor** (Set baud rate to `115200`).

#### Option B: Using Command Line (arduino-cli)
Run the compile command:
```powershell
& "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 "firmware\SIEIS_ESP32\SIEIS_ESP32.ino"
```
And upload to COM4:
```powershell
& "C:\Users\insan\Downloads\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM4 --fqbn esp32:esp32:esp32 "firmware\SIEIS_ESP32\SIEIS_ESP32.ino"
```

### Step 6: Launch the Python Backend Server
Start the Flask backend in PowerShell:
```powershell
.\.venv\Scripts\python.exe backend\app.py
```
*Expected Output:*
```
[INFO] sieis.database: Initialized SIEIS database schema successfully on backend/data/sieis.db
[INFO] sieis.server: Starting SIEIS Server on 0.0.0.0:5000 (Debug=False)
 * Running on http://127.0.0.1:5000
 * Running on http://10.40.222.63:5000
```

### Step 7: Verify Backend Health
In your web browser or in a separate PowerShell window, check the health endpoint:
```powershell
curl.exe http://localhost:5000/health
```
*Expected Response:*
```json
{
  "database_status": "connected",
  "device_freshness": { "is_connected": true, "is_stale": false },
  "service": "SIEIS Backend",
  "status": "healthy"
}
```

### Step 8: Open the Live Web Dashboard
Open your browser and navigate to:
```
http://localhost:5000/
```
Or from any device connected to the same phone hotspot:
```
http://10.40.222.63:5000/
```

---

## 3. Running Automated Tests
To run the full suite of 31 automated backend, database, validation, intelligence, and simulation tests:
```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## 4. Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **ESP32 Serial says `[HTTP] POST failed, error: connection refused`** | Backend server is not running, or listening on wrong IP | Ensure `app.py` is running. Check that your laptop's Wi-Fi IP matches `config.h`. |
| **ESP32 Serial says `[Wi-Fi] Warning: Connection timeout`** | Hotspot SSID/password incorrect or band mismatch | Verify credentials in `config.h`. Ensure your phone hotspot is set to **2.4 GHz band** (ESP32 does not support 5 GHz Wi-Fi). |
| **Dashboard displays `Telemetry Stale (>30s)`** | ESP32 has stopped transmitting or lost power | Check USB cable connection. Open Serial Monitor to confirm loop execution. |
| **Upload error: `A fatal error occurred: Could not open COM4`** | COM4 is currently open in another program (e.g. Serial Monitor) | Close the Serial Monitor window before clicking Upload. |
| **Windows Firewall blocks ESP32 connection** | Windows private network firewall is blocking port 5000 | In PowerShell (Admin), allow port 5000: `New-NetFirewallRule -DisplayName "SIEIS Server" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow`. *(Do NOT turn off firewall entirely).* |
| **MQ-135 shows "Warming Up"** | Device was just powered on | The MQ-135 requires 5 minutes to stabilize its heater. The dashboard will automatically transition to "Ready" after 300 seconds. |
