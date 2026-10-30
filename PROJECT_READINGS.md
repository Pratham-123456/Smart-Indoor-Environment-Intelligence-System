# SIEIS Project Sensor Telemetry Readings

> Single dedicated reference document containing only the physical sensor readings acquired by the SIEIS hardware edge node (esp32-sieis-01).

---

## 1. Hardware Sensors & Measurement Summary Table

| Sensor Channel | Physical Hardware | Measurement Parameter | Unit / Format | Min Recorded | Max Recorded | Average | Nominal Operating Range |
|---|---|---|---|---|---|---|---|
| **Temperature** | DHT22 (Aosong AM2302) | Ambient Dry-Bulb Temperature | °C | 23.3 °C | 42.0 °C | 27.9 °C | 21.0 - 24.0 °C (Optimal) |
| **Relative Humidity** | DHT22 (Capacitive RH) | Ambient Relative Humidity | % RH | 38.9 % | 78.4 % | 57.0 % | 40.0 - 60.0 % (Optimal) |
| **Ambient Light** | Photoresistor (LDR + 10kΩ Divider) | Relative Surface Brightness | Raw ADC Count (0-4095) | 0 | 2957 | 695 | 250 - 1700 (Dim to Bright) |
| **Air Quality / Gas** | Hanwei MQ-135 (SnO₂ Metal Oxide) | Total Reducing Gas Response | Millivolts (mV) | 289 mV | 4725 mV | 513 mV | 300 - 650 mV (Clean Air Baseline) |
| **Acoustic Noise** | Electret Mic + LM393 Comparator | Peak-to-Peak Swing (150ms window) | Amplitude Counts (0-4095) | 78 | 564 | 248 | 100 - 350 (Normal Ambient) |

- **Target Hardware ID**: esp32-sieis-01
- **Total Valid Observations Logged**: 4,311 samples
- **Data Collection Window**: 2026-10-19 04:26:32 IST to 2026-10-29 23:07:41 IST

---

## 2. Recent Sensor Telemetry Log (Chronological Sample)

| Packet ID | Sequence # | Timestamp (IST) | Temp (°C) | Humidity (%) | Light (ADC) | Light Class | MQ-135 (mV) | MQ Status | Sound Swing | Digital Mic DO |
|---|---|---|---|---|---|---|---|---|---|---|
| #4483 | seq-54 | 2026-10-29 23:07:41 IST | 27.6 °C | 65.4 % | 335 | dim | 709 mV | warming_up | 233 | 0 |
| #4482 | seq-53 | 2026-10-29 23:07:36 IST | 27.6 °C | 65.2 % | 333 | dim | 712 mV | warming_up | 179 | 0 |
| #4481 | seq-52 | 2026-10-29 23:07:31 IST | 27.6 °C | 65.2 % | 321 | dim | 718 mV | warming_up | 181 | 0 |
| #4480 | seq-51 | 2026-10-29 23:07:26 IST | 27.5 °C | 65.4 % | 334 | dim | 720 mV | warming_up | 165 | 0 |
| #4479 | seq-50 | 2026-10-29 23:07:21 IST | 27.5 °C | 65.3 % | 335 | dim | 733 mV | warming_up | 179 | 0 |
| #4478 | seq-49 | 2026-10-29 23:07:16 IST | 27.6 °C | 65.4 % | 336 | dim | 739 mV | warming_up | 183 | 0 |
| #4477 | seq-48 | 2026-10-29 23:07:11 IST | 27.5 °C | 65.3 % | 341 | dim | 744 mV | warming_up | 167 | 0 |
| #4476 | seq-47 | 2026-10-29 23:07:06 IST | 27.5 °C | 65.4 % | 326 | dim | 736 mV | warming_up | 233 | 0 |
| #4475 | seq-46 | 2026-10-29 23:07:01 IST | 27.6 °C | 65.4 % | 345 | dim | 744 mV | warming_up | 159 | 0 |
| #4474 | seq-45 | 2026-10-29 23:06:56 IST | 27.5 °C | 65.6 % | 351 | dim | 754 mV | warming_up | 203 | 0 |
| #4473 | seq-44 | 2026-10-29 23:06:51 IST | 27.5 °C | 65.8 % | 321 | dim | 781 mV | warming_up | 206 | 0 |
| #4472 | seq-43 | 2026-10-29 23:06:46 IST | 27.5 °C | 65.5 % | 377 | dim | 754 mV | warming_up | 202 | 0 |
| #4471 | seq-42 | 2026-10-29 23:06:41 IST | 27.5 °C | 65.5 % | 418 | dim | 913 mV | warming_up | 223 | 0 |
| #4470 | seq-41 | 2026-10-29 23:06:36 IST | 27.5 °C | 65.4 % | 402 | dim | 915 mV | warming_up | 238 | 0 |
| #4469 | seq-40 | 2026-10-29 23:06:31 IST | 27.6 °C | 65.6 % | 383 | dim | 886 mV | warming_up | 206 | 0 |
| #4468 | seq-39 | 2026-10-29 23:06:26 IST | 27.5 °C | 65.6 % | 320 | dim | 924 mV | warming_up | 199 | 0 |
| #4467 | seq-38 | 2026-10-29 23:06:21 IST | 27.5 °C | 65.8 % | 317 | dim | 919 mV | warming_up | 504 | 0 |
| #4466 | seq-37 | 2026-10-29 23:06:16 IST | 27.5 °C | 65.5 % | 39 | dark | 1000 mV | warming_up | 181 | 0 |
| #4465 | seq-36 | 2026-10-29 23:06:11 IST | 27.5 °C | 65.5 % | 208 | dark | 994 mV | warming_up | 229 | 0 |
| #4464 | seq-35 | 2026-10-29 23:06:06 IST | 27.5 °C | 65.8 % | 232 | dark | 997 mV | warming_up | 273 | 0 |
| #4463 | seq-34 | 2026-10-29 23:06:01 IST | 27.4 °C | 65.9 % | 247 | dark | 1017 mV | warming_up | 193 | 0 |
| #4462 | seq-33 | 2026-10-29 23:05:57 IST | 27.4 °C | 66.1 % | 240 | dark | 1054 mV | warming_up | 223 | 0 |
| #4461 | seq-872 | 2026-10-27 17:23:22 IST | 29.8 °C | 59.1 % | 1688 | dim | 336 mV | ready | 264 | 0 |
| #4460 | seq-871 | 2026-10-27 17:23:17 IST | 29.7 °C | 58.9 % | 1695 | dim | 333 mV | ready | 214 | 0 |
| #4459 | seq-870 | 2026-10-27 17:23:12 IST | 29.8 °C | 58.9 % | 1786 | bright | 334 mV | ready | 226 | 0 |
| #4458 | seq-869 | 2026-10-27 17:23:07 IST | 29.8 °C | 59.0 % | 1795 | bright | 334 mV | ready | 223 | 0 |
| #4457 | seq-868 | 2026-10-27 17:23:02 IST | 29.8 °C | 58.9 % | 1784 | bright | 334 mV | ready | 259 | 0 |
| #4456 | seq-867 | 2026-10-27 17:22:57 IST | 29.8 °C | 59.0 % | 1793 | bright | 319 mV | ready | 247 | 0 |
| #4455 | seq-866 | 2026-10-27 17:22:52 IST | 29.8 °C | 59.0 % | 1797 | bright | 312 mV | ready | 221 | 0 |
| #4454 | seq-865 | 2026-10-27 17:22:47 IST | 29.8 °C | 59.1 % | 1717 | bright | 309 mV | ready | 256 | 0 |
| #4453 | seq-864 | 2026-10-27 17:22:42 IST | 29.8 °C | 59.1 % | 1741 | bright | 310 mV | ready | 219 | 0 |
| #4452 | seq-863 | 2026-10-27 17:22:37 IST | 29.8 °C | 59.1 % | 1703 | bright | 309 mV | ready | 246 | 0 |
| #4451 | seq-862 | 2026-10-27 17:22:32 IST | 29.8 °C | 58.9 % | 1647 | dim | 309 mV | ready | 249 | 0 |
| #4450 | seq-861 | 2026-10-27 17:22:27 IST | 29.9 °C | 59.1 % | 1685 | dim | 309 mV | ready | 214 | 0 |
| #4449 | seq-860 | 2026-10-27 17:22:22 IST | 29.9 °C | 58.9 % | 1727 | bright | 309 mV | ready | 251 | 0 |
| #4448 | seq-859 | 2026-10-27 17:22:17 IST | 29.8 °C | 59.0 % | 1715 | bright | 309 mV | ready | 236 | 0 |
| #4447 | seq-858 | 2026-10-27 17:22:12 IST | 29.9 °C | 59.0 % | 1636 | dim | 309 mV | ready | 233 | 0 |
| #4446 | seq-857 | 2026-10-27 17:22:07 IST | 29.9 °C | 59.0 % | 1694 | dim | 310 mV | ready | 271 | 0 |
| #4445 | seq-856 | 2026-10-27 17:22:02 IST | 29.8 °C | 59.0 % | 1732 | bright | 310 mV | ready | 212 | 0 |
| #4444 | seq-855 | 2026-10-27 17:21:57 IST | 29.8 °C | 59.0 % | 1692 | dim | 310 mV | ready | 236 | 0 |
| #4443 | seq-854 | 2026-10-27 17:21:52 IST | 29.8 °C | 58.9 % | 1671 | dim | 310 mV | ready | 216 | 0 |
| #4442 | seq-853 | 2026-10-27 17:21:47 IST | 29.9 °C | 58.9 % | 1694 | dim | 310 mV | ready | 232 | 0 |
| #4441 | seq-852 | 2026-10-27 17:21:42 IST | 29.9 °C | 58.9 % | 1744 | bright | 310 mV | ready | 301 | 0 |
| #4440 | seq-851 | 2026-10-27 17:21:37 IST | 29.9 °C | 58.9 % | 1711 | bright | 309 mV | ready | 225 | 0 |
| #4439 | seq-850 | 2026-10-27 17:21:32 IST | 29.9 °C | 59.0 % | 1670 | dim | 310 mV | ready | 232 | 0 |
| #4438 | seq-849 | 2026-10-27 17:21:27 IST | 29.9 °C | 59.1 % | 1680 | dim | 310 mV | ready | 235 | 0 |
| #4437 | seq-848 | 2026-10-27 17:21:22 IST | 29.9 °C | 58.9 % | 1729 | bright | 310 mV | ready | 228 | 0 |
| #4436 | seq-847 | 2026-10-27 17:21:17 IST | 29.9 °C | 59.0 % | 1657 | dim | 312 mV | ready | 268 | 0 |
| #4435 | seq-846 | 2026-10-27 17:21:12 IST | 29.9 °C | 59.0 % | 1610 | dim | 312 mV | ready | 240 | 0 |
| #4434 | seq-845 | 2026-10-27 17:21:07 IST | 29.9 °C | 59.1 % | 1678 | dim | 312 mV | ready | 218 | 0 |

---
*Generated automatically from SIEIS Persistence Engine (ackend/data/sieis.db).*