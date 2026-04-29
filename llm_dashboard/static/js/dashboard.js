        let isPaused = false;
        let refreshInterval;

        function escapeHtml(text) {
            const d = document.createElement('div');
            d.textContent = text;
            return d.innerHTML;
        }

        async function fetchData() {
            if (isPaused) return;
            
            try {
                const response = await fetch('/api/data');
                if (!response.ok) {
                    console.error('API returned status ' + response.status);
                    return;
                }
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Failed to fetch data:', error);
            }
        }

        function updateDashboard(data) {
            document.getElementById('model-name').textContent = data.active_on_8080 === 'vllm' ? (data.model_on_8080 || data.model_name) : (data.model_name || 'Unknown');
            document.getElementById('cpu-load').textContent = data.cpu.load + '%';

            document.getElementById('ram-usage').textContent = `${data.ram.used.toFixed(1)} / ${data.ram.total.toFixed(1)} GB`;
            document.getElementById('ram-percent').textContent = `${data.ram.percent.toFixed(1)}%`;

            const servicesStatus = document.getElementById('services-status');
            servicesStatus.innerHTML = '';
            const promptRate = data.prompt_tokens_per_second;
            const generationRate = data.generation_tokens_per_second;
            for (const [service, status] of Object.entries(data.services)) {
                const wrapper = document.createElement('div');
                wrapper.style.marginBottom = '8px';
                
                const badge = document.createElement('span');
                const badgeClass = status === 'UP' ? 'service-up'
                    : status === 'SLOW' ? 'service-slow'
                    : status === 'UNRESPONSIVE' ? 'service-unresponsive'
                    : status === 'LOADING' ? 'service-loading'
                    : 'service-down';
                badge.className = `service-badge ${badgeClass}`;
                const statusText = status === 'UP' ? 'ACTIVE' : status;
                badge.textContent = `${service}: ${statusText}`;
                wrapper.appendChild(badge);
                
                const llamaSvc = data.active_llama_service_name || data.llama_service_name;
                const isLlamaActive = (data.active_on_8080 === 'ik_llama_cpp' || data.active_on_8080 === 'llama_cpp');
                if (service === llamaSvc && isLlamaActive && status === 'UP') {
                    if (typeof data.slots_active === 'number' && typeof data.slots_total === 'number' && data.slots_total > 0) {
                        const slotsLine = document.createElement('div');
                        slotsLine.style.fontSize = '11px';
                        slotsLine.style.marginTop = '4px';
                        const slotsClass = data.slots_active < data.slots_total ? 'slot-available' : 'slot-full';
                        slotsLine.innerHTML = `Active Slots: <span class="${slotsClass}">${data.slots_active} / ${data.slots_total}</span>`;
                        wrapper.appendChild(slotsLine);
                    }
                }

                if (service === llamaSvc && isLlamaActive && (status === 'UP' || status === 'LOADING') && data.model_name && data.model_name !== 'Unknown') {
                    const modelName = document.createElement('div');
                    modelName.style.fontSize = '11px';
                    modelName.style.color = '#8b949e';
                    modelName.style.marginTop = '4px';
                    modelName.textContent = `Model: ${data.model_name}`;
                    wrapper.appendChild(modelName);
                }

                if (service === data.vllm_service_name && data.active_on_8080 === 'vllm' && status === 'UP') {
                    const vllmModel = document.createElement('div');
                    vllmModel.style.fontSize = '11px';
                    vllmModel.style.color = '#8b949e';
                    vllmModel.style.marginTop = '4px';
                    vllmModel.textContent = `Model: ${data.model_on_8080 || 'Unknown'}`;
                    wrapper.appendChild(vllmModel);
                }

                if (service === llamaSvc && isLlamaActive && (status === 'UP' || status === 'SLOW' || status === 'UNRESPONSIVE')) {
                    const hasPrompt = Number.isFinite(data.prompt_tokens_per_second);
                    const hasGeneration = Number.isFinite(data.generation_tokens_per_second);
                    if (hasPrompt || hasGeneration) {
                        const speedLine = document.createElement('div');
                        speedLine.style.fontSize = '11px';
                        speedLine.style.color = '#8b949e';
                        speedLine.style.marginTop = '4px';
                        const promptText = hasPrompt ? `${data.prompt_tokens_per_second.toFixed(2)} tok/s` : 'n/a';
                        const generationText = hasGeneration ? `${data.generation_tokens_per_second.toFixed(2)} tok/s` : 'n/a';
                        speedLine.textContent = `Prompt: ${promptText} | Gen: ${generationText}`;
                        wrapper.appendChild(speedLine);
                    }
                }

                if (service === data.vllm_service_name && data.active_on_8080 === 'vllm' && (status === 'UP' || status === 'SLOW')) {
                    const hasPrompt = Number.isFinite(data.vllm_prompt_tokens_per_second);
                    const hasGeneration = Number.isFinite(data.vllm_generation_tokens_per_second);
                    if (hasPrompt || hasGeneration) {
                        const speedLine = document.createElement('div');
                        speedLine.style.fontSize = '11px';
                        speedLine.style.color = '#8b949e';
                        speedLine.style.marginTop = '4px';
                        const promptText = hasPrompt ? `${data.vllm_prompt_tokens_per_second.toFixed(2)} tok/s` : 'n/a';
                        const generationText = hasGeneration ? `${data.vllm_generation_tokens_per_second.toFixed(2)} tok/s` : 'n/a';
                        speedLine.textContent = `Prompt: ${promptText} | Gen: ${generationText}`;
                        wrapper.appendChild(speedLine);
                    }
                }

                if (service === llamaSvc && isLlamaActive && data.llama_state === 'LOADING') {
                    const loadingLine = document.createElement('div');
                    loadingLine.style.fontSize = '11px';
                    loadingLine.style.color = '#8b949e';
                    loadingLine.style.marginTop = '4px';
                    const elapsed = formatDuration(data.llama_loading_seconds);
                    const eta = data.llama_eta_seconds === null ? 'n/a' : formatDuration(data.llama_eta_seconds);
                    loadingLine.textContent = `Loading: ${elapsed} elapsed | ETA: ${eta}`;
                    wrapper.appendChild(loadingLine);
                }

                if (service === llamaSvc && isLlamaActive && data.client_ips && data.client_ips.length > 0) {
                    const lastIp = data.client_ips[data.client_ips.length - 1];
                    const ipLine = document.createElement('div');
                    ipLine.style.fontSize = '11px';
                    ipLine.style.color = '#58a6ff';
                    ipLine.style.marginTop = '4px';
                    ipLine.innerHTML = `<strong>Last Client IP:</strong> ${escapeHtml(lastIp)}`;
                    wrapper.appendChild(ipLine);
                }

                servicesStatus.appendChild(wrapper);
            }

            const gpuCards = document.getElementById('gpu-cards');
            gpuCards.innerHTML = '';
            data.gpus.forEach(gpu => {
                const vramPercent = gpu.memory.total > 0 ? (gpu.memory.used / gpu.memory.total) * 100 : 0;
                const vramClass = vramPercent > vramDanger ? 'danger' : vramPercent > vramWarning ? 'warning' : '';
                
                const powerPercent = gpu.power_limit > 0 ? (gpu.power / gpu.power_limit) * 100 : 0;
                const powerClass = powerPercent > powerDanger ? 'danger' : powerPercent > powerWarning ? 'warning' : '';
                
                const card = document.createElement('div');
                card.className = 'gpu-card';
                card.setAttribute('data-gpu', gpu.id);
                card.innerHTML = `
                    <h3>${escapeHtml(gpu.name)} (ID: ${escapeHtml(String(gpu.id))})</h3>
                    <div class="gpu-stats">
                        <div class="gpu-stat">Temp: ${gpu.temp}&deg;C</div>
                        <div class="gpu-stat">Fan: ${gpu.fan}%</div>
                        <div class="gpu-stat">GPU Util: ${gpu.gpu_util}%</div>
                    </div>
                    <div class="power-gauge">
                        <div class="gpu-stat">Power Draw: ${gpu.power.toFixed(1)}W / ${gpu.power_limit}W</div>
                        <div class="power-bar">
                            <div class="power-fill ${powerClass}" style="width: ${powerPercent}%"></div>
                        </div>
                        <div class="power-text">${powerPercent.toFixed(1)}% of limit</div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div class="gpu-stat">GPU Utilization: ${gpu.gpu_util}%</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${gpu.gpu_util}%"></div>
                        </div>
                    </div>
                    <div style="margin-top: 10px;">
                        <div class="gpu-stat">VRAM: ${gpu.memory.used.toFixed(1)} / ${gpu.memory.total.toFixed(1)} GiB</div>
                        <div class="progress-bar">
                            <div class="progress-fill ${vramClass}" style="width: ${vramPercent}%"></div>
                        </div>
                        <div style="margin-top: 5px; font-size: 12px;">VRAM: ${vramPercent.toFixed(1)}%</div>
                    </div>
                    ${gpu.sm_clock != null ? '<div class="gpu-stat" style="margin-top:8px;">SM: ' + gpu.sm_clock + ' MHz' + (gpu.throttled ? ' <span class="gpu-warn">\u26A0 throttled</span>' : '') + '</div>' : ''}
                    ${gpu.mem_clock != null ? '<div class="gpu-stat">Mem: ' + gpu.mem_clock + ' MHz</div>' : ''}
                    ${gpu.vram_temp != null ? '<div class="gpu-stat">VRAM Temp: ' + gpu.vram_temp.toFixed(0) + '\u00B0C</div>' : ''}
                    ${gpu.encoder_util != null ? '<div class="gpu-stat">Enc: ' + gpu.encoder_util + '% / Dec: ' + (gpu.decoder_util || 0) + '%</div>' : ''}
                `;
                gpuCards.appendChild(card);
            });

            updateLogTabs(data);
            // F12: Dynamic title, F16: GPU summary, F11: Threshold alerts
            updateTabTitle(data);
            updateGpuSummary(data);
            applyThresholdAlerts(data);
        }

        function updateLogTabs(data) {
            const panelsContainer = document.getElementById('logs-panels');
            const serviceOrder = data.service_order || Object.keys(data.service_logs || {});
            const serviceNames = data.service_names || {};
            const serviceLogs = data.service_logs || {};

            const existingPanels = panelsContainer.querySelectorAll('.logs-panel');
            const existingKeys = Array.from(existingPanels).map(p => p.dataset.service);
            const newKeys = serviceOrder;

            if (JSON.stringify(existingKeys) !== JSON.stringify(newKeys)) {
                panelsContainer.innerHTML = '';
            }

            serviceOrder.forEach(svcKey => {
                const logs = serviceLogs[svcKey] || [];
                const svcName = serviceNames[svcKey] || svcKey;
                const svcStatus = data.services[svcName] || 'DOWN';
                const isUp = svcStatus === 'UP' || svcStatus === 'ACTIVE' || svcStatus === 'SLOW';
                const isLoading = svcStatus === 'LOADING';
                let dotColor = '#da3633';
                if (isUp) dotColor = '#238636';
                else if (isLoading) dotColor = '#d29922';

                let panel = panelsContainer.querySelector(`[data-service="${svcKey}"]`);
                const logContent = logs.join(String.fromCharCode(10));

                if (!panel) {
                    panel = document.createElement('div');
                    panel.className = 'logs-panel';
                    panel.dataset.service = svcKey;
                    const header = document.createElement('div');
                    header.className = 'logs-panel-header';
                    const dot = document.createElement('span');
                    dot.className = 'tab-dot';
                    dot.innerHTML = '&#9679;';
                    dot.style.color = dotColor;
                    dot.dataset.role = 'dot';
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

                const dot = panel.querySelector('[data-role="dot"]');
                if (dot) dot.style.color = dotColor;

                const logDiv = panel.querySelector('.logs-container');
                if (!logDiv) return;
                const wasAtBottom = logDiv.scrollTop + logDiv.clientHeight >= logDiv.scrollHeight - 20;
                const prevContent = logDiv._prevContent || '';
                if (logContent !== prevContent) {
                    logDiv.textContent = '';
                    logs.forEach(log => {
                        const line = document.createElement('div');
                        line.className = 'log-line';
                        line.textContent = log;
                        logDiv.appendChild(line);
                    });
                    logDiv._prevContent = logContent;
                }
                if (wasAtBottom) {
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
            });
        }

        document.getElementById('pause-btn').addEventListener('click', function() {
            isPaused = !isPaused;
            this.textContent = isPaused ? 'Resume Refresh' : 'Pause Refresh';
            this.classList.toggle('paused', isPaused);
        });

        function formatDuration(seconds) {
            if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return 'n/a';
            const total = Math.max(0, Math.round(seconds));
            const hours = Math.floor(total / 3600);
            const minutes = Math.floor((total % 3600) / 60);
            const secs = total % 60;
            if (hours > 0) {
                return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            }
            return `${minutes}:${String(secs).padStart(2, '0')}`;
        }

        const _cfg = window.DASHBOARD_CONFIG || {};
        const vramWarning = _cfg.vramWarningPercent || 70;
        const vramDanger = _cfg.vramDangerPercent || 90;
        const powerWarning = _cfg.powerWarningPercent || 70;
        const powerDanger = _cfg.powerDangerPercent || 90;

        // F12: Dynamic tab title
        function updateTabTitle(data) {
            const downCount = Object.values(data.services || {}).filter(s => s === 'DOWN').length;
            const model = data.model_name && data.model_name !== 'Unknown' ? data.model_name : null;
            if (downCount > 0) {
                document.title = '\u26A0 ' + downCount + ' DOWN — Dashboard';
            } else if (model) {
                document.title = model + ' — Dashboard';
            } else {
                document.title = 'System & AI Dashboard';
            }
        }

        // F16: Multi-GPU aggregate summary
        function updateGpuSummary(data) {
            const gpus = data.gpus || [];
            let existing = document.getElementById('gpu-summary');
            if (gpus.length <= 1) {
                if (existing) existing.remove();
                return;
            }
            if (!existing) {
                existing = document.createElement('div');
                existing.id = 'gpu-summary';
                existing.style.cssText = 'text-align:center;color:#8b949e;font-size:12px;margin-bottom:10px;';
                const gpuSection = document.getElementById('gpu-cards');
                if (gpuSection) gpuSection.parentNode.insertBefore(existing, gpuSection);
            }
            let totalVram = 0, totalPower = 0, maxTemp = 0;
            gpus.forEach(g => {
                if (g.memory) totalVram += g.memory.used || 0;
                totalPower += g.power || 0;
                if (g.temp > maxTemp) maxTemp = g.temp;
            });
            let totalVramGb = 0;
            gpus.forEach(g => { if (g.memory) totalVramGb += g.memory.total || 0; });
            existing.textContent = gpus.length + ' GPU · VRAM: ' + totalVram.toFixed(1) + ' / ' + totalVramGb.toFixed(0) + ' GiB · Temp max: ' + maxTemp + '\u00B0C · Power: ' + totalPower.toFixed(0) + 'W';
        }

        // F11: Visual alerts — apply threshold-based coloring
        function applyThresholdAlerts(data) {
            const gpus = data.gpus || [];
            const dVram = vramDanger || 90, wVram = vramWarning || 70;
            const dPower = powerDanger || 90, wPower = powerWarning || 70;
            gpus.forEach((gpu, idx) => {
                const vramPct = gpu.memory && gpu.memory.total > 0 ? (gpu.memory.used / gpu.memory.total) * 100 : 0;
                const powerPct = gpu.power_limit > 0 ? (gpu.power / gpu.power_limit) * 100 : 0;
                const card = document.querySelector('.gpu-card[data-gpu="' + idx + '"]');
                if (!card) return;
                if (vramPct > dVram || powerPct > dPower) card.style.borderColor = '#da3633';
                else if (vramPct > wVram || powerPct > wPower) card.style.borderColor = '#d29922';
                else card.style.borderColor = '#238636';
            });
        }

        refreshInterval = setInterval(fetchData, (_cfg.refreshIntervalMs || 1000));
        fetchData();
