        let serviceStates = {};
        let isPolling = true;
        const LLM_KEYS = new Set((() => {
            const states = (window.ADMIN_INITIAL_STATE && window.ADMIN_INITIAL_STATE.services) || {};
            return Object.keys(states).filter(k => states[k].is_llm);
        })());

        function showToast(message, isError) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + (isError ? 'error' : 'success');
            setTimeout(() => toast.className = 'toast', 4000);
        }

        // Timers: {key: {startTime:number, intervalId:number, label:string}}
        let actionTimers = {};

        function startTimer(key, label) {
            stopTimer(key);
            const start = Date.now();
            const display = document.getElementById('timer-' + key) || document.getElementById('llm-timer');
            actionTimers[key] = {
                startTime: start,
                intervalId: setInterval(() => {
                    const secs = Math.floor((Date.now() - start) / 1000);
                    const m = Math.floor(secs / 60).toString().padStart(2, '0');
                    const s = (secs % 60).toString().padStart(2, '0');
                    if (display) {
                        display.textContent = label + ' : ' + m + ':' + s;
                        display.className = 'timer-display timer-active';
                    }
                }, 1000),
                label: label
            };
        }

        function stopTimer(key) {
            if (actionTimers[key]) {
                clearInterval(actionTimers[key].intervalId);
                const display = document.getElementById('timer-' + key);
                if (display) {
                    display.className = 'timer-display timer-done';
                }
                delete actionTimers[key];
            }
        }

        async function handleAction(key, action) {
            const btnStart = document.getElementById('start-btn-' + key);
            const btnStop  = document.getElementById('stop-btn-' + key);
            const btnForce = document.getElementById('force-btn-' + key);
            if (btnStart) btnStart.disabled = true;
            if (btnStop)  btnStop.disabled = true;
            if (btnForce) btnForce.disabled = true;

            if (action === 'start') startTimer(key, 'Demarrage en cours');
            if (action === 'stop') startTimer(key, 'Arret en cours');
            if (action === 'force_stop') startTimer(key, 'Force kill en cours');

            try {
                let response;
                if (action === 'force_stop') {
                    response = await fetch('/api/admin/force_stop', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ service: key })
                    });
                } else {
                    response = await fetch('/api/admin/' + action, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ service: key })
                    });
                }
                const data = await response.json();
                if (data.success) {
                    showToast(data.message, false);
                } else {
                    showToast(data.message || 'Erreur inconnue', true);
                }
            } catch (err) {
                showToast('Erreur reseau : ' + err.message, true);
            }
            setTimeout(() => { stopTimer(key); refreshStatus(); }, 500);
        }

        async function handleLLM(action) {
            const select = document.getElementById('llm-select');
            const key = select.value;
            if (!key) {
                showToast('Veuillez choisir un modele dans la liste', true);
                return;
            }
            const btnStart = document.getElementById('llm-start-btn');
            const btnRestart = document.getElementById('llm-restart-btn');
            const btnStop = document.getElementById('llm-stop-btn');
            const btnForce = document.getElementById('llm-force-btn');
            if (btnStart) btnStart.disabled = true;
            if (btnRestart) btnRestart.disabled = true;
            if (btnStop) btnStop.disabled = true;
            if (btnForce) btnForce.disabled = true;

            if (action === 'start') startTimer('llm', 'Demarrage en cours');
            if (action === 'restart') startTimer('llm', 'Redemarrage en cours');
            if (action === 'stop') startTimer('llm', 'Arret en cours');
            if (action === 'force_stop') startTimer('llm', 'Force kill en cours');

            try {
                let url = '/api/admin/' + action;
                let body = JSON.stringify({ service: key });
                if (action === 'restart') {
                    url = '/api/admin/restart';
                }
                let response = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: body
                });
                const data = await response.json();
                if (data.success) {
                    showToast(data.message, false);
                } else {
                    showToast(data.message || 'Erreur inconnue', true);
                }
            } catch (err) {
                showToast('Erreur reseau : ' + err.message, true);
            }
            setTimeout(() => { stopTimer('llm'); refreshStatus(); }, 500);
        }

        async function stopAllLLM() {
            try {
                const response = await fetch('/api/admin/stop_all_llm', {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                const data = await response.json();
                if (data.success) {
                    showToast('Tous les LLM ont ete arretes.', false);
                } else {
                    showToast('Erreur arret LLM.', true);
                }
            } catch (err) {
                showToast('Erreur reseau : ' + err.message, true);
            }
            setTimeout(() => refreshStatus(), 500);
        }

        document.getElementById('stop-all-llm').addEventListener('click', stopAllLLM);

        async function refreshStatus() {
            if (!isPolling) return;
            try {
                const response = await fetch('/api/admin/status', { credentials: 'same-origin' });
                if (!response.ok) return;
                const data = await response.json();
                updateUI(data);
            } catch (err) {
                console.error('refreshStatus error:', err);
            }
        }

        function updateUI(data) {
            const services = data.services || {};
            const llmSelect = document.getElementById('llm-select');
            const llmStart = document.getElementById('llm-start-btn');
            const llmRestart = document.getElementById('llm-restart-btn');
            const llmStop = document.getElementById('llm-stop-btn');
            const llmForce = document.getElementById('llm-force-btn');

            let anyLLMRunning = false;
            let runningLLM = null;
            const vram = data.vram || {};
            const serviceLogs = data.service_logs || {};

            for (const [key, svc] of Object.entries(services)) {
                if (svc.is_llm && svc.port === 8080) {
                    if (svc.running) {
                        anyLLMRunning = true;
                        runningLLM = svc.display_name;
                        // Stop timer if it finished starting
                        if (actionTimers['llm']) {
                            stopTimer('llm');
                        }
                    }
                    continue;  // LLM port 8080 managed by dropdown
                }
                const dot = document.getElementById('dot-' + key);
                const btnStart = document.getElementById('start-btn-' + key);
                const btnStop  = document.getElementById('stop-btn-' + key);
                const btnForce = document.getElementById('force-btn-' + key);
                if (dot) dot.style.color = svc.running ? '#238636' : '#da3633';
                if (btnStart) btnStart.disabled = svc.running;
                if (btnStop)  btnStop.disabled = !svc.running;
                if (btnForce) btnForce.disabled = !svc.running;
                if (svc.running) stopTimer(key);
            }

            // Update dropdown state for LLM port 8080
            if (llmStart) llmStart.disabled = anyLLMRunning;
            if (llmRestart) llmRestart.disabled = !anyLLMRunning;
            if (llmStop) llmStop.disabled = !anyLLMRunning;
            if (llmForce) llmForce.disabled = !anyLLMRunning;
            if (llmSelect) {
                if (anyLLMRunning) {
                    llmSelect.disabled = true;
                } else {
                    llmSelect.disabled = false;
                }
                // Select the running LLM option
                if (runningLLM) {
                    for (const opt of llmSelect.options) {
                        const svc = services[opt.value];
                        if (svc && svc.running) {
                            opt.selected = true;
                            break;
                        }
                    }
                }
            }
            const runningEl = document.getElementById('running-llm');
            if (runningEl) {
                runningEl.textContent = runningLLM ? 'LLM actif : ' + runningLLM : 'Aucun LLM actif';
            }
            // Update VRAM bar
            const vramContent = document.getElementById('vram-content');
            if (vramContent && vram && vram.enabled) {
                let html = '';
                let totalUsed = 0;
                if (vram.error) {
                    html = '<div class="gpu-line gpu-warn">Erreur VRAM : ' + escapeHtml(vram.error) + '</div>';
                } else if (vram.gpus) {
                    for (const gpu of vram.gpus) {
                        const up = gpu.usage_percent > 90 ? 'gpu-danger' : (gpu.usage_percent > 70 ? 'gpu-warn' : 'gpu-ok');
                        const label = gpu.usage_percent > 90 ? 'CRITIQUE' : (gpu.usage_percent > 70 ? 'Attention' : 'OK');
                        totalUsed += gpu.used_mb;
                        html += '<div class="gpu-line">GPU ' + escapeHtml(String(gpu.index)) + ' (' + escapeHtml(gpu.name) + '): '
                             + gpu.used_mb.toFixed(0) + ' MiB utilise / ' + gpu.total_mb.toFixed(0) + ' MiB total = '
                             + gpu.free_mb.toFixed(0) + ' MiB libres ('
                             + gpu.usage_percent.toFixed(1) + '%) <span class="' + up + '">' + label + '</span></div>';
                    }
                }
                // Conseil d'arret
                const adviceEl = document.getElementById('vram-advice');
                if (adviceEl) {
                    if (totalUsed > 500) {
                        adviceEl.innerHTML = '<span class="vram-risk">ATTENTION — VRAM utilisee : ' + totalUsed.toFixed(0) + ' MiB au total. Il reste probablement des residus GPU. Pensez a utiliser "Force Kill" si l' + String.fromCharCode(39) + 'arret normal ne libere pas la VRAM.</span>';
                    } else {
                        adviceEl.innerHTML = '<span class="vram-safe">VRAM quasi-libre (' + totalUsed.toFixed(0) + ' MiB). Arret sans risque possible.</span>';
                    }
                }
                vramContent.innerHTML = html;
            }
                        // Update logs - simple version sans mapping statut
            if (serviceLogs) {
                const panelsContainer = document.getElementById('logs-panels');
                const serviceOrder = data.service_order || Object.keys(serviceLogs);
                const serviceNames = data.service_names || {};

                const existingPanels = panelsContainer.querySelectorAll('.logs-panel');
                const existingKeys = Array.from(existingPanels).map(p => p.dataset.service);
                if (JSON.stringify(existingKeys) !== JSON.stringify(serviceOrder)) {
                    panelsContainer.innerHTML = '';
                }

                for (const svcKey of serviceOrder) {
                    const logs = serviceLogs[svcKey] || [];
                    const svcName = serviceNames[svcKey] || svcKey;

                    let panel = panelsContainer.querySelector(`[data-service="${svcKey}"]`);
                    if (!panel) {
                        panel = document.createElement('div');
                        panel.className = 'logs-panel';
                        panel.dataset.service = svcKey;
                        const header = document.createElement('div');
                        header.className = 'logs-panel-header';
                        const dot = document.createElement('span');
                        dot.className = 'tab-dot';
                        dot.style.color = '#238636';
                        dot.textContent = '•';
                        const name = document.createElement('span');
                        name.className = 'panel-name';
                        name.textContent = svcName;
                        header.appendChild(dot);
                        header.appendChild(name);
                        panel.appendChild(header);
                        const logDiv = document.createElement('div');
                        logDiv.className = 'logs-container';
                        panel.appendChild(logDiv);
                        panelsContainer.appendChild(panel);
                    }

                    const logDiv = panel.querySelector('.logs-container');
                    if (!logDiv) continue;
                    const wasAtBottom = logDiv.scrollTop + logDiv.clientHeight >= logDiv.scrollHeight - 20;
                    const logContent = logs.join(String.fromCharCode(10));
                    const prevContent = logDiv._prevContent || '';
                    if (logContent !== prevContent) {
                        logDiv.innerHTML = '';
                        if (logs.length > 0) {
                            for (const line of logs) {
                                const lineEl = document.createElement('div');
                                lineEl.className = 'log-line';
                                lineEl.textContent = line;
                                logDiv.appendChild(lineEl);
                            }
                        } else {
                            const emptyEl = document.createElement('div');
                            emptyEl.className = 'log-empty';
                            emptyEl.textContent = '(logs vides ou fichier inexistant)';
                            logDiv.appendChild(emptyEl);
                        }
                        logDiv._prevContent = logContent;
                    }
                    if (wasAtBottom) {
                        logDiv.scrollTop = logDiv.scrollHeight;
                    }
                }
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        setInterval(refreshStatus, 2000);
        refreshStatus();
