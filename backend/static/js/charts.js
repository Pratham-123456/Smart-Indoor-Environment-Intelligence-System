/**
 * SIEIS Dashboard Charts Module (Chart.js Integration)
 */

const SieisCharts = {
    thermalChart: null,
    gasChart: null,
    lightSoundChart: null,
    ehsChart: null,

    initCharts() {
        const defaultScales = {
            x: {
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', maxTicksLimit: 6 }
            },
            y: {
                grid: { color: '#1e293b' },
                ticks: { color: '#94a3b8' }
            }
        };

        // 1. Thermal & Humidity Chart
        const ctxThermal = document.getElementById('chart-thermal')?.getContext('2d');
        if (ctxThermal) {
            this.thermalChart = new Chart(ctxThermal, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Temp (°C)',
                            data: [],
                            borderColor: '#f97316',
                            backgroundColor: 'rgba(249, 115, 22, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Humidity (%)',
                            data: [],
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: {
                        x: defaultScales.x,
                        y: {
                            type: 'linear',
                            position: 'left',
                            grid: { color: '#1e293b' },
                            ticks: { color: '#f97316' },
                            suggestedMin: 15,
                            suggestedMax: 35
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#38bdf8' },
                            suggestedMin: 20,
                            suggestedMax: 80
                        }
                    }
                }
            });
        }

        // 2. MQ-135 Gas Response vs Baseline
        const ctxGas = document.getElementById('chart-gas')?.getContext('2d');
        if (ctxGas) {
            this.gasChart = new Chart(ctxGas, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Gas Response (pin mV)',
                            data: [],
                            borderColor: '#eab308',
                            backgroundColor: 'rgba(234, 179, 8, 0.1)',
                            borderWidth: 2,
                            tension: 0.3
                        },
                        {
                            label: 'Rolling Baseline (mV)',
                            data: [],
                            borderColor: '#a855f7',
                            borderDash: [5, 5],
                            borderWidth: 2,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: defaultScales
                }
            });
        }

        // 3. Light & Sound Activity Chart
        const ctxLS = document.getElementById('chart-light-sound')?.getContext('2d');
        if (ctxLS) {
            this.lightSoundChart = new Chart(ctxLS, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'LDR Raw (ADC)',
                            data: [],
                            borderColor: '#facc15',
                            borderWidth: 2,
                            tension: 0.3,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Sound Swing (150ms)',
                            data: [],
                            borderColor: '#ec4899',
                            borderWidth: 2,
                            tension: 0.3,
                            yAxisID: 'y'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: {
                        x: defaultScales.x,
                        y: {
                            grid: { color: '#1e293b' },
                            ticks: { color: '#94a3b8' },
                            min: 0,
                            max: 4095
                        }
                    }
                }
            });
        }

        // 4. Environmental Health & Comfort Scores Chart
        const ctxEhs = document.getElementById('chart-ehs')?.getContext('2d');
        if (ctxEhs) {
            this.ehsChart = new Chart(ctxEhs, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Health Score (EHS)',
                            data: [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.15)',
                            fill: true,
                            borderWidth: 2,
                            tension: 0.3
                        },
                        {
                            label: 'Comfort Index',
                            data: [],
                            borderColor: '#6366f1',
                            borderWidth: 2,
                            tension: 0.3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#cbd5e1' } } },
                    scales: {
                        x: defaultScales.x,
                        y: {
                            grid: { color: '#1e293b' },
                            ticks: { color: '#10b981' },
                            min: 0,
                            max: 100
                        }
                    }
                }
            });
        }
    },

    updateCharts(readings, currentBaselineMv) {
        if (!readings || readings.length === 0) return;

        const labels = readings.map(r => {
            if (!r.received_at) return '';
            const d = new Date(r.received_at);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        });

        // Update Thermal
        if (this.thermalChart) {
            this.thermalChart.data.labels = labels;
            this.thermalChart.data.datasets[0].data = readings.map(r => r.temperature_c);
            this.thermalChart.data.datasets[1].data = readings.map(r => r.humidity_percent);
            this.thermalChart.update('none');
        }

        // Update Gas
        if (this.gasChart) {
            this.gasChart.data.labels = labels;
            this.gasChart.data.datasets[0].data = readings.map(r => r.mq135_adc_mv);
            this.gasChart.data.datasets[1].data = readings.map(() => currentBaselineMv || null);
            this.gasChart.update('none');
        }

        // Update Light & Sound
        if (this.lightSoundChart) {
            this.lightSoundChart.data.labels = labels;
            this.lightSoundChart.data.datasets[0].data = readings.map(r => r.light_raw);
            this.lightSoundChart.data.datasets[1].data = readings.map(r => r.sound_swing);
            this.lightSoundChart.update('none');
        }
    },

    updateScoreHistory(historyLabels, ehsScores, comfortScores) {
        if (this.ehsChart && historyLabels.length > 0) {
            this.ehsChart.data.labels = historyLabels;
            this.ehsChart.data.datasets[0].data = ehsScores;
            this.ehsChart.data.datasets[1].data = comfortScores;
            this.ehsChart.update('none');
        }
    }
};
