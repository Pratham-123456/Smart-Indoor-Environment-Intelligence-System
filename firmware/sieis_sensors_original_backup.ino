// SIEIS - all sensor readings (Serial Monitor, 115200 baud)
// Board: ESP32 Dev Module
// Libraries: "DHT sensor library" by Adafruit + "Adafruit Unified Sensor"
//
// Pins:
//   DHT22 DATA  -> GPIO4   (3-pin board, powered from 3V3)
//   LDR divider -> GPIO35  (LDR to 3V3, 10k to GND, junction to GPIO35)
//   MQ-135 AO   -> GPIO34  (through 10k + 2x10k divider, MQ-135 on 5V)
//   Sound AO    -> GPIO32
//   Sound DO    -> GPIO26

#include <DHT.h>

#define DHT_PIN    4
#define LDR_PIN    35
#define MQ_PIN     34
#define SOUND_AO   32
#define SOUND_DO   26

#define MQ_WARMUP_MS 300000UL   // ignore MQ-135 for the first 5 minutes after power-up

DHT dht(DHT_PIN, DHT22);

float lastTemp = NAN;
float lastHum  = NAN;

int avgRead(int pin, int samples = 16) {
  long sum = 0;
  for (int i = 0; i < samples; i++) sum += analogRead(pin);
  return sum / samples;
}

int avgMilliVolts(int pin, int samples = 32) {
  long sum = 0;
  for (int i = 0; i < samples; i++) sum += analogReadMilliVolts(pin);
  return sum / samples;
}

// Peak-to-peak swing of the sound module's analog output over 150 ms
int soundSwing() {
  int peak = 0, low = 4095;
  unsigned long start = millis();
  while (millis() - start < 150) {
    int v = analogRead(SOUND_AO);
    if (v > peak) peak = v;
    if (v < low) low = v;
  }
  return peak - low;
}


const char* lightLabel(int level) {
  if (level < 250)  return "dark";
  if (level < 1000) return "dim";
  return "bright";
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();
  pinMode(SOUND_DO, INPUT);

  analogReadResolution(12);
  analogSetPinAttenuation(MQ_PIN, ADC_11db);
  analogSetPinAttenuation(LDR_PIN, ADC_11db);
  analogSetPinAttenuation(SOUND_AO, ADC_11db);

  Serial.println("SIEIS sensor test started");
}

void loop() {
  // DHT22: keep the last good value if one read fails
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  bool dhtOk = !(isnan(t) || isnan(h));
  if (dhtOk) {
    lastTemp = t;
    lastHum = h;
  }

  int ldr = avgRead(LDR_PIN);

  int mqPinMv = avgMilliVolts(MQ_PIN);
  int mqAoMv  = (int)(mqPinMv * 1.5);   // undo the 10k : 20k divider (approximate)
  bool mqReady = millis() > MQ_WARMUP_MS;

  int swing = soundSwing();
  int soundDo = digitalRead(SOUND_DO);

  if (dhtOk) Serial.printf("Temp=%.1fC Hum=%.1f%%", lastTemp, lastHum);
  else if (!isnan(lastTemp)) Serial.printf("Temp=%.1fC Hum=%.1f%% (DHT22 read failed, old value)", lastTemp, lastHum);
  else Serial.print("DHT22 READ FAILED");

  Serial.printf(" | Light=%d (%s)", ldr, lightLabel(ldr));
  Serial.printf(" | MQ135 pin=%dmV AO~%dmV%s", mqPinMv, mqAoMv, mqReady ? "" : " (warming up)");
  Serial.printf(" | Sound swing=%d DO=%d\n", swing, soundDo);

  delay(1850);   // total loop time is about 2 s, the DHT22 minimum between reads
}
