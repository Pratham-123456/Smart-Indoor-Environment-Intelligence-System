/**
 * SIEIS — Smart Indoor Environmental Intelligence System
 * Integrated ESP32 Edge Firmware (Wi-Fi + HTTP Telemetry)
 * 
 * Hardware Target: ESP32 Dev Module (CP210x on COM4)
 * Baud Rate: 115200
 * Required Libraries (Arduino Library Manager):
 *   - "DHT sensor library" by Adafruit
 *   - "Adafruit Unified Sensor" by Adafruit
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

#if __has_include("config.h")
  #include "config.h"
#else
  #include "config.example.h"
#endif

// Sensor object
DHT dht(DHT_PIN, DHT22);

// Cached readings for resilience
float lastTemp = NAN;
float lastHum  = NAN;

// Telemetry & State Machine Tracking
unsigned long lastTelemetryTime = 0;
unsigned long lastWifiRetryTime = 0;
uint32_t sequenceNumber = 0;

// ==========================================
// Sensor Acquisition Helpers
// ==========================================

int avgRead(int pin, int samples = 16) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
  }
  return (int)(sum / samples);
}

int avgMilliVolts(int pin, int samples = 32) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogReadMilliVolts(pin);
  }
  return (int)(sum / samples);
}

// Peak-to-peak swing of the sound module's analog output over a 150 ms sample window
int soundSwing() {
  int peak = 0;
  int low = 4095;
  unsigned long start = millis();
  while (millis() - start < 150) {
    int v = analogRead(SOUND_AO);
    if (v > peak) peak = v;
    if (v < low)  low = v;
  }
  return peak - low;
}

const char* lightLabel(int level) {
  if (level < LDR_DARK_THRESH) return "dark";
  if (level < LDR_DIM_THRESH)  return "dim";
  return "bright";
}

// ==========================================
// Network Management
// ==========================================

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("\n[Wi-Fi] Connecting to hotspot: " WIFI_SSID " ...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[Wi-Fi] Connected successfully!");
    Serial.print("[Wi-Fi] ESP32 Assigned IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[Wi-Fi] Warning: Connection timeout. Continuing in local acquisition mode.");
  }
}

void checkWiFiReconnection() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiRetryTime > 30000UL) {
      lastWifiRetryTime = millis();
      Serial.println("[Wi-Fi] Attempting background reconnection...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
  }
}

// ==========================================
// HTTP Telemetry Transmission
// ==========================================

bool transmitTelemetry(
  float temp, float hum, bool dhtOk,
  int ldr, const char* ldrLabel,
  int mqPinMv, int mqAoMv, bool mqReady,
  int swing, int soundDo
) {
  // Construct JSON payload
  char jsonBuffer[600];
  char tempStr[16];
  char humStr[16];

  if (!isnan(temp)) snprintf(tempStr, sizeof(tempStr), "%.2f", temp);
  else snprintf(tempStr, sizeof(tempStr), "null");

  if (!isnan(hum)) snprintf(humStr, sizeof(humStr), "%.2f", hum);
  else snprintf(humStr, sizeof(humStr), "null");

  sequenceNumber++;
  unsigned long uptime = millis();

  snprintf(
    jsonBuffer, sizeof(jsonBuffer),
    "{"
      "\"device_id\":\"%s\","
      "\"firmware_version\":\"%s\","
      "\"sequence_number\":%u,"
      "\"uptime_ms\":%lu,"
      "\"temperature_c\":%s,"
      "\"humidity_percent\":%s,"
      "\"light_raw\":%d,"
      "\"light_label\":\"%s\","
      "\"mq135_adc_mv\":%d,"
      "\"mq135_sensor_mv\":%d,"
      "\"mq135_status\":\"%s\","
      "\"sound_swing\":%d,"
      "\"sound_do\":%d,"
      "\"sensor_status\":{\"dht22\":\"%s\",\"ldr\":\"ok\",\"mq135\":\"%s\",\"sound\":\"ok\"},"
      "\"pressure_hpa\":null,"
      "\"eco2_ppm\":null,"
      "\"tvoc_ppb\":null,"
      "\"aqi\":null"
    "}",
    DEVICE_ID,
    FIRMWARE_VERSION,
    sequenceNumber,
    uptime,
    tempStr,
    humStr,
    ldr,
    ldrLabel,
    mqPinMv,
    mqAoMv,
    mqReady ? "ready" : "warming_up",
    swing,
    soundDo,
    dhtOk ? "ok" : "degraded_cached",
    mqReady ? "ready" : "warming_up"
  );

  // Always emit structured JSON to USB Serial for direct bridge ingestion
  Serial.print("[JSON] ");
  Serial.println(jsonBuffer);

  // Over-the-air Wi-Fi HTTP POST
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Wi-Fi offline. Ingesting via USB Serial Bridge.");
    return false;
  }

  HTTPClient http;
  http.begin(BACKEND_SERVER_URL);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST((uint8_t*)jsonBuffer, strlen(jsonBuffer));
  bool success = false;

  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_CREATED || httpCode == HTTP_CODE_OK) {
      Serial.printf("[HTTP] POST Success (seq=%u, HTTP %d)\n", sequenceNumber, httpCode);
      success = true;
    } else {
      Serial.printf("[HTTP] Warning: Server returned HTTP %d: %s\n", httpCode, http.getString().c_str());
    }
  } else {
    Serial.printf("[HTTP] POST failed, error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  return success;
}

// ==========================================
// Setup and Main Loop
// ==========================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n==================================================");
  Serial.println("  SIEIS — Smart Indoor Environmental Intelligence");
  Serial.println("  Firmware v" FIRMWARE_VERSION " Initializing...");
  Serial.println("==================================================");

  // Initialize Sensors
  dht.begin();
  pinMode(SOUND_DO, INPUT);

  // Configure ADC (12-bit, 0-3.3V attenuation)
  analogReadResolution(12);
  analogSetPinAttenuation(MQ_PIN, ADC_11db);
  analogSetPinAttenuation(LDR_PIN, ADC_11db);
  analogSetPinAttenuation(SOUND_AO, ADC_11db);

  Serial.println("[Sensors] ADC resolution and attenuations configured.");
  Serial.printf("[Sensors] MQ-135 Warmup Window: %lu seconds.\n", MQ_WARMUP_MS / 1000UL);

  // Initialize Network
  connectToWiFi();

  Serial.println("[System] Boot completed. Commencing periodic telemetry cycle.\n");
}

void loop() {
  checkWiFiReconnection();

  unsigned long currentMillis = millis();
  if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = currentMillis;

    // 1. Read DHT22
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    bool dhtOk = !(isnan(t) || isnan(h));
    if (dhtOk) {
      lastTemp = t;
      lastHum = h;
    }

    // 2. Read Bare LDR
    int ldr = avgRead(LDR_PIN);
    const char* ldrStr = lightLabel(ldr);

    // 3. Read MQ-135
    int mqPinMv = avgMilliVolts(MQ_PIN);
    int mqAoMv  = (int)(mqPinMv * 1.5);   // 10k:20k voltage divider conversion
    bool mqReady = currentMillis > MQ_WARMUP_MS;

    // 4. Read Sound Module
    int swing = soundSwing();
    int soundDo = digitalRead(SOUND_DO);

    // 5. Serial Diagnostics
    Serial.println("------------------------------------------------------------------");
    if (dhtOk) {
      Serial.printf("[DHT22] Temp: %.1f C | Hum: %.1f %%\n", lastTemp, lastHum);
    } else if (!isnan(lastTemp)) {
      Serial.printf("[DHT22] Temp: %.1f C | Hum: %.1f %% (Cached fallback; read timed out)\n", lastTemp, lastHum);
    } else {
      Serial.println("[DHT22] Read Failed; no cached reading available.");
    }

    Serial.printf("[LDR]   Raw ADC: %d (%s)\n", ldr, ldrStr);
    Serial.printf("[MQ135] Pin: %d mV | Ao: ~%d mV | Status: %s\n", mqPinMv, mqAoMv, mqReady ? "READY" : "WARMING UP");
    Serial.printf("[SOUND] Swing (150ms): %d | DO: %d (%s)\n", swing, soundDo, soundDo == 1 ? "ACTIVE" : "QUIET");

    // 6. Transmit to Python Backend
    transmitTelemetry(
      lastTemp, lastHum, dhtOk,
      ldr, ldrStr,
      mqPinMv, mqAoMv, mqReady,
      swing, soundDo
    );
  }

  delay(50); // Yield to background FreeRTOS watchdog & Wi-Fi tasks
}
