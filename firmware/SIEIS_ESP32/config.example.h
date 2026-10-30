/**
 * SIEIS (Smart Indoor Environmental Intelligence System)
 * Firmware Configuration Template
 * 
 * Instructions:
 * 1. Copy this file to "config.h" in the same directory:
 *    cp config.example.h config.h
 * 2. Edit "config.h" with your Wi-Fi credentials and laptop IP address.
 * 3. Never commit "config.h" or your real passwords to version control.
 */

#ifndef SIEIS_CONFIG_H
#define SIEIS_CONFIG_H

// ==========================================
// Network Credentials (Phone Hotspot / Wi-Fi)
// ==========================================
#define WIFI_SSID             "YOUR_WIFI_HOTSPOT_SSID"
#define WIFI_PASSWORD         "YOUR_WIFI_PASSWORD"

// ==========================================
// Centralized Backend Endpoint
// (Check laptop IPv4 on the hotspot via PowerShell: Get-NetIPAddress)
// ==========================================
#define BACKEND_SERVER_URL    "http://10.40.222.63:5000/api/sensor"
#define HTTP_TIMEOUT_MS       4000

// ==========================================
// Node Identification & Telemetry Timing
// ==========================================
#define DEVICE_ID             "esp32-sieis-01"
#define FIRMWARE_VERSION      "1.0.0"
#define TELEMETRY_INTERVAL_MS 5000UL  // Data transmission interval (5 seconds)

// ==========================================
// Pin Assignments (Verified Hardware Baseline)
// ==========================================
#define DHT_PIN               4       // DHT22 Data pin (powered from 3V3)
#define LDR_PIN               35      // Bare LDR analog divider junction
#define MQ_PIN                34      // MQ-135 AO through 10k:20k divider
#define SOUND_AO              32      // LM393 Sound sensor analog output
#define SOUND_DO              26      // LM393 Sound sensor digital threshold

// ==========================================
// Calibration & Operational Thresholds
// ==========================================
#define MQ_WARMUP_MS          300000UL  // 5 minutes (300,000 ms) sensor heater warmup
#define LDR_DARK_THRESH       250       // ADC < 250 = Dark
#define LDR_DIM_THRESH        1700      // ADC 250..1699 = Dim, >= 1700 = Bright

#endif // SIEIS_CONFIG_H
