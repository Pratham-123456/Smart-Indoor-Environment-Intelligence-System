# SIEIS Intelligence & Analytics Engine Specification

## 1. Executive Summary
The intelligence engine is the foundational differentiator of SIEIS, elevating the platform above traditional "dumb" sensor dashboards. It provides:
1. Explainable, multi-parameter environmental ratings (**Environmental Health Score** & **Comfort Index**).
2. Dynamic **Rolling Baseline Adaptation** for relative gas-response monitoring.
3. Automated **Trend Detection** and rates of change per minute.
4. Rule-based **Anomaly Detection** with alert deduplication and hysteresis.
5. Qualified **Short-Horizon Trend Extrapolations** (forecasting).
6. Actionable **Decision Support** generating practical room interventions.

---

## 2. Comfort Index Algorithm

### 2.1 Thermal Comfort Formulation ($S_T$)
Based on ASHRAE 55 and CIBSE indoor temperature standards for sedentary occupants:
- **Optimal Range:** $20.0^\circ\text{C} \le T \le 25.0^\circ\text{C} \implies S_T = 100\%$
- **Acceptable Lower Margin ($18.0 \le T < 20.0$):**
  $$S_T = 70.0 + 30.0 \times \frac{T - 18.0}{20.0 - 18.0}$$
- **Acceptable Upper Margin ($25.0 < T \le 27.0$):**
  $$S_T = 70.0 + 30.0 \times \frac{27.0 - T}{27.0 - 25.0}$$
- **Sub-optimal Drops:** Linear descent to 0% at $T \le 10^\circ\text{C}$ or $T \ge 35^\circ\text{C}$.

### 2.2 Hygric Comfort Formulation ($S_H$)
- **Optimal Range:** $40.0\% \le H \le 60.0\% \implies S_H = 100\%$
- **Acceptable Lower Margin ($30.0 \le H < 40.0$):**
  $$S_H = 70.0 + 30.0 \times \frac{H - 30.0}{40.0 - 30.0}$$
- **Acceptable Upper Margin ($60.0 < H \le 70.0$):**
  $$S_H = 70.0 + 30.0 \times \frac{70.0 - H}{70.0 - 60.0}$$
- **Sub-optimal Drops:** Linear descent to 0% at $H \le 15\%$ or $H \ge 85\%$.

### 2.3 Synthesis
$$\text{Comfort Index} = 0.55 \cdot S_T + 0.45 \cdot S_H$$
- $\ge 85.0$: `COMFORTABLE`
- $65.0 \dots 84.9$: `SLIGHTLY_UNCOMFORTABLE`
- $< 65.0$: `UNCOMFORTABLE`

---

## 3. Environmental Health Score (EHS)

The EHS synthesizes four environmental pillars into a holistic rating:

| Pillar | Subsystem | Default Weight ($w_i$) | Component Valuation |
|---|---|---|---|
| **Thermal-Hygric Comfort** | DHT22 | 0.40 | Derived directly from Comfort Index |
| **Gas Response Balance** | MQ-135 vs Baseline | 0.30 | Ratio $R = \frac{V_{pin}}{V_{baseline}}$ |
| **Visual Lighting Quality** | Bare LDR | 0.15 | Categorical classification score |
| **Acoustic Disturbance** | LM393 Sound Swing | 0.15 | 150ms peak-to-peak amplitude penalty |

### 3.1 Gas Response Component Valuation
If MQ-135 is in `ready` state and baseline is established:
- $R \le 1.05$: Score $= 100.0$ (Clean air baseline)
- $1.05 < R \le 1.25$: Score $= 100.0 - 25.0 \times \frac{R - 1.05}{0.20}$ (Mild elevation)
- $1.25 < R \le 1.50$: Score $= 75.0 - 35.0 \times \frac{R - 1.25}{0.25}$ (Moderate elevation)
- $R > 1.50$: Score $= \max(10.0, 40.0 - 30.0 \times (R - 1.50))$ (Severe surge)

*Note: If MQ-135 is warming up or baseline is unavailable, this component is excluded, and remaining weights are re-normalized:*
$$\text{EHS} = \sum_{i \in \text{available}} S_i \times \frac{w_i}{\sum_{j \in \text{available}} w_j}$$

### 3.2 Grade Thresholds
- **OPTIMAL:** $85.0 \dots 100.0$
- **GOOD:** $70.0 \dots 84.9$
- **FAIR:** $50.0 \dots 69.9$
- **POOR:** $30.0 \dots 49.9$
- **CRITICAL:** $0.0 \dots 29.9$

---

## 4. MQ-135 Rolling Baseline Algorithm

Chemiresistive metal-oxide sensors drift with ambient humidity and long-term surface aging. Therefore, static absolute voltage thresholds cause either false positives or missed events.

SIEIS implements an adaptive rolling baseline:
1. **Sample Gathering:** Gathers the last $N = 30$ valid, non-warmup readings.
2. **Trimmed Mean Filter:** Sorts readings and trims the upper and lower 20% of samples. This prevents an acute spike (e.g. transient deodorant or solvent) from immediately pulling the baseline upwards.
3. **Persisted Record:** Updates `mq135_baseline_history` with sample count and window size.

---

## 5. Trend Analysis & Rate of Change
For any continuous signal $y(t)$:
- **Short-Term Simple Moving Average (SMA-5):** $\text{SMA}_5 = \frac{1}{5}\sum_{k=0}^4 y_{n-k}$
- **Long-Term Simple Moving Average (SMA-15):** $\text{SMA}_{15} = \frac{1}{15}\sum_{k=0}^{14} y_{n-k}$
- **Finite-Difference Rate of Change per Minute:**
  $$\frac{dy}{dt} \approx \frac{y_n - y_0}{\Delta t_{\text{minutes}}}$$
- **Classification:**
  - $\frac{dy}{dt} > \theta_{\text{stability}} \implies \text{RISING}$
  - $\frac{dy}{dt} < -\theta_{\text{stability}} \implies \text{FALLING}$
  - Otherwise $\implies \text{STABLE}$

---

## 6. Ordinary Least Squares (OLS) Linear Trend Forecasting
For short-horizon projections (+5, +10, +15 minutes):
- Requires at least $N \ge 8$ chronologically ordered observations within the active window.
- Fits line $y = m \cdot t + c$ minimizing residual sum of squares:
  $$m = \frac{\sum (t_i - \bar{t})(y_i - \bar{y})}{\sum (t_i - \bar{t})^2}$$
- **Quality Assessment ($R^2$):**
  $$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$$
- **Safeguards:** Values are physically clamped within plausible bounds (e.g., humidity bounded between 0% and 100%).
- **Qualification:** The system explicitly states that this is a linear trend extrapolation of observed sensor quantities, not an unconstrained future simulation.
