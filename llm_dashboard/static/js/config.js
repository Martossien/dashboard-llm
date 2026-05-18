function getCsrfHeaders() {
    const cfg = window.ADMIN_CONFIG || {};
    const token = cfg.csrfToken || '';
    const header = cfg.csrfHeader || 'X-CSRF-Token';
    return token ? { [header]: token } : {};
}

function toast(msg, isError) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast ' + (isError ? 'error' : 'success');
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 4000);
}

function switchTab(name) {
    document.querySelectorAll('.config-tab').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.config-panel').forEach(el => el.classList.remove('active'));
    document.querySelector(`.config-tab[data-tab="${name}"]`).classList.add('active');
    document.getElementById('panel-' + name).classList.add('active');
    if (name === 'add') {
        const keyInput = document.getElementById('svc-key');
        if (!keyInput.value) {
            keyInput.readOnly = false;
            keyInput.style.opacity = '1';
            document.getElementById('svc-key-hint').textContent = 'Ex: vllm_qwen27b, llama_heretic, claude_code_proxy';
        }
    } else if (name === 'services') {
        loadServices();
    }
}

// ===================== AUDIT =====================

async function doAudit() {
    const results = document.getElementById('audit-results');
    results.innerHTML = '<p style="color:#8b949e;">Scan en cours...</p>';
    try {
        const resp = await fetch('/api/admin/config/audit', { credentials: 'same-origin' });
        const data = await resp.json();
        renderAudit(data);
    } catch (e) {
        results.innerHTML = '<p style="color:#f85149;">Erreur: ' + e.message + '</p>';
    }
}

function renderAudit(d) {
    const r = document.getElementById('audit-results');
    let html = '';

    // Backends
    html += '<div class="audit-section"><h4>Backends trouves (cliquez pour selectionner)</h4>';
    for (const [name, info] of Object.entries(d.backends || {})) {
        const cls = info.found ? 'found' : 'missing';
        const icon = info.found ? '✅' : '❌';
        const path = info.path ? ' (' + info.path + ')' : '';
        const click = info.found ? `onclick="selectBackend('${escAttr(name)}')" style="cursor:pointer"` : '';
        html += `<span class="audit-item ${cls}" ${click}>${icon} ${escHtml(name)}${escHtml(path)}</span>`;
    }
    html += '</div>';

    // Models
    const totalModels = (d.models || []).length;
    const lmCount = d.lm_studio_model_count || 0;
    html += `<div class="audit-section"><h4>Modeles trouves — ${totalModels} au total (${lmCount} via LM Studio) — cliquez pour selectionner</h4>`;
    if ((d.models || []).length > 0) {
        const localModels = (d.models || []).filter(m => m.source !== 'lmstudio').slice(0, 8);
        const lmModels = (d.models || []).filter(m => m.source === 'lmstudio').slice(0, 6);
        localModels.forEach(m => {
            const gb = m.size_gb ? ` (${m.size_gb} GB)` : '';
            const fc = m.file_count > 1 ? ` (${m.file_count} fichiers${m.sharded ? ', sharded' : ''})` : '';
            const modelPath = m.first_gguf || m.path;
            html += `<span class="audit-item found" onclick="selectModel('${escAttr(modelPath)}','${escAttr(m.name)}')" style="cursor:pointer" title="${escAttr(m.path)}">📁 ${escHtml(m.name)}${escHtml(gb)}${escHtml(fc)}</span>`;
        });
        if (lmModels.length > 0) {
            html += '<br><span style="color:#d29922;font-size:11px;">📦 LM Studio:</span> ';
            lmModels.forEach(m => {
                const fc = m.file_count > 1 ? ` (${m.file_count} fichiers${m.sharded ? ', sharded' : ''})` : '';
                const modelPath = m.first_gguf || m.path;
                html += `<span class="audit-item found" onclick="selectModel('${escAttr(modelPath)}','${escAttr(m.name)}')" style="cursor:pointer;border-color:#d29922;" title="${escAttr(m.path)}">📦 ${escHtml(m.name)}${escHtml(fc)}</span>`;
            });
            if (lmCount > 6) html += `<span class="audit-item missing">+${lmCount - 6} autres</span>`;
        }
    } else { html += '<span class="audit-item missing">Aucun modele trouve</span>'; }
    html += '</div>';

    // Conda
    html += '<div class="audit-section"><h4>Environnements Conda</h4>';
    const llmEnvs = (d.conda_envs || []).filter(e => ['vllm', 'sglang', 'llama', 'ollama', 'comfyui', 'whisper'].some(k => e.name.includes(k)));
    llmEnvs.forEach(e => { html += `<span class="audit-item found">🐍 ${e.name}</span>`; });
    html += '</div>';

    // Ports
    html += '<div class="audit-section"><h4>Ports LLM ouverts (8000-30100) — cliquez pour selectionner</h4>';
    (d.ports_open || []).forEach(p => { html += `<span class="audit-item found" onclick="selectPort(${p})" style="cursor:pointer">🔌 ${p}</span>`; });
    if (!d.ports_open || d.ports_open.length === 0) html += '<span class="audit-item missing">Aucun</span>';
    html += '</div>';

    // Systemd
    html += '<div class="audit-section"><h4>Services systemd</h4>';
    const llmUnits = (d.systemd_units || []).filter(u => ['vllm', 'llama', 'ollama', 'sglang', 'proxy', 'voxtral', 'whisper', 'comfy'].some(k => u.includes(k)));
    llmUnits.forEach(u => { html += `<span class="audit-item found">⚙ ${u}</span>`; });
    html += '</div>';

    // GPUs
    html += '<div class="audit-section"><h4>GPUs</h4>';
    (d.gpus || []).forEach(g => {
        const gb = (g.memory_total_mb / 1024).toFixed(1);
        html += `<span class="audit-item found">🖥 GPU ${escAttr(String(g.index))}: ${escAttr(g.name)} (${escAttr(gb)} GiB)</span>`;
    });
    html += '</div>';

    r.innerHTML = html;
}

function selectBackend(backend) {
    switchTab('add');
    document.getElementById('svc-backend').value = backend;
    onBackendChange();
    if (backend === 'ollama' || backend === 'lmstudio') {
        document.getElementById('svc-role').value = 'llm';
    }
    toast('Backend ' + backend + ' selectionne. Remplissez les champs restants.');
}

function selectModel(path, name) {
    switchTab('add');
    document.getElementById('svc-model').value = path;
    if (!document.getElementById('svc-name').value || document.getElementById('svc-name').value === document.getElementById('svc-key').value) {
        document.getElementById('svc-name').value = name;
    }
    document.getElementById('svc-logfile').value = '/var/log/' + name.replace(/[/\s]/g, '_') + '.log';
    toast('Modele selectionne: ' + name);
}

function selectPort(port) {
    switchTab('add');
    document.getElementById('svc-port').value = port;
    document.getElementById('svc-url').value = 'http://127.0.0.1:' + port;
    toast('Port ' + port + ' selectionne.');
}

function escAttr(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escHtml(s) {
    return escAttr(s);
}

// ===================== ADD SERVICE =====================

const LOG_FILTER_DESCRIPTIONS = {
    'vllm': 'Filtre les access logs uvicorn (GET /health, /metrics, /v1/models).',
    'ik_llama.cpp': 'Filtre les lignes repetitives llama.cpp (srv stop, slots idle, etc.).',
    'llama.cpp': 'Filtre les lignes repetitives llama.cpp (srv stop, slots idle, etc.).',
    'proxy': 'Filtre les access logs werkzeug, les 404 /metrics, les redirects /login et les health checks repetitifs.',
    'ollama': 'Aucun filtre supplementaire (journalctl).',
    'sglang': 'Aucun filtre supplementaire.',
    'lmstudio': 'Aucun filtre supplementaire.',
    'gradio': 'Filtre les access logs, les 404 /metrics et les health checks repetitifs.',
};

function onLogFilterChange() {
    const sel = document.getElementById('svc-log-filter');
    const info = document.getElementById('log-filter-info');
    if (sel.value === 'verbose') {
        info.textContent = 'Mode verbose : aucune ligne de log ne sera filtree. Utile pour le debug.';
    } else {
        const backend = document.getElementById('svc-backend').value;
        const desc = LOG_FILTER_DESCRIPTIONS[backend] || 'Filtre les lignes de log inutiles selon le backend.';
        info.textContent = desc;
    }
}

function onBackendChange() {
    const backend = document.getElementById('svc-backend').value;
    const descs = {
        'vllm': 'Chargeur Python pour modeles BF16/FP8. KillMode=mixed (processus enfants). ~15 min de chargement.',
        'llama.cpp': 'Chargeur C++ pour fichiers GGUF. KillMode=process. ~1-2 min de chargement.',
        'ik_llama.cpp': 'Fork de llama.cpp avec MTP et optimisations. KillMode=process.',
        'sglang': 'Chargeur Python OpenAI-compatible. KillMode=process. ~10 min de chargement.',
        'ollama': 'Service systemd multi-modeles. Demande a la demande. KillMode=process.',
        'lmstudio': 'Application desktop. Port par defaut 1234. API OpenAI-compatible. KillMode=process.',
        'proxy': 'Proxy API. Pas de modele, pas de VRAM.',
        'gradio': 'Interface WebUI Gradio. Pas de VRAM sauf si charge un modele (ex: STT).'
    };
    document.getElementById('backend-info').textContent = descs[backend] || '';

    onLogFilterChange();

    fetch('/api/admin/config/backend-defaults?backend=' + backend, {credentials:'same-origin'})
    .then(r => r.json())
    .then(defs => {
        if (defs.exec_start_template && !document.getElementById('svc-exec-start').value) {
            document.getElementById('svc-exec-start').value = defs.exec_start_template;
        }
        if (defs.health_endpoint && !document.getElementById('svc-health-endpoint').value) {
            document.getElementById('svc-health-endpoint').value = defs.health_endpoint;
        }
        if (defs.models_endpoint && !document.getElementById('svc-models-endpoint').value) {
            document.getElementById('svc-models-endpoint').value = defs.models_endpoint;
        }
        if (defs.timeout_seconds && !document.getElementById('svc-timeout').value) {
            document.getElementById('svc-timeout').value = defs.timeout_seconds;
        }
        if (defs.startup_time_seconds && !document.getElementById('svc-startup-time').value) {
            document.getElementById('svc-startup-time').value = defs.startup_time_seconds;
        }
        if (defs.process_patterns && defs.process_patterns.length && !document.getElementById('svc-process-patterns').value) {
            document.getElementById('svc-process-patterns').value = defs.process_patterns.join(', ');
        }
    }).catch(() => {});
}

function suggestUnit() {
    const key = document.getElementById('svc-key').value || 'mon-service';
    document.getElementById('svc-unit').value = key + '.service';
    document.getElementById('svc-url').value = 'http://127.0.0.1:' + (document.getElementById('svc-port').value || '8000');
}

function _clearForm() {
    document.getElementById('svc-key').value = '';
    document.getElementById('svc-key').readOnly = false;
    document.getElementById('svc-key').style.opacity = '1';
    document.getElementById('svc-key-hint').textContent = 'Ex: vllm_qwen27b, llama_heretic, claude_code_proxy';
    document.getElementById('svc-name').value = '';
    document.getElementById('svc-role').value = 'llm';
    document.getElementById('svc-backend').value = 'vllm';
    document.getElementById('svc-port').value = '';
    document.getElementById('svc-url').value = '';
    document.getElementById('svc-health-endpoint').value = '';
    document.getElementById('svc-models-endpoint').value = '';
    document.getElementById('svc-timeout').value = '';
    document.getElementById('svc-unit').value = '';
    document.getElementById('svc-model').value = '';
    document.getElementById('svc-exec-start').value = '';
    document.getElementById('svc-logfile').value = '';
    document.getElementById('svc-log-filter').value = 'default';
    document.getElementById('svc-startup-time').value = '';
    document.getElementById('svc-model-detect').value = '';
    document.getElementById('svc-process-patterns').value = '';
    document.getElementById('svc-process-exclude').value = '';
    document.getElementById('svc-start-command').value = '';
    document.getElementById('svc-stop-command').value = '';
    document.getElementById('svc-group').value = '';
}

function _collectServiceData() {
    const startCmd = document.getElementById('svc-start-command').value.trim();
    const stopCmd = document.getElementById('svc-stop-command').value.trim();
    const procPatterns = document.getElementById('svc-process-patterns').value.trim();
    const procExclude = document.getElementById('svc-process-exclude').value.trim();
    const data = {
        key: document.getElementById('svc-key').value.trim(),
        name: document.getElementById('svc-name').value || document.getElementById('svc-key').value.trim(),
        backend: document.getElementById('svc-backend').value,
        role: document.getElementById('svc-role').value,
        base_url: document.getElementById('svc-url').value,
        port: parseInt(document.getElementById('svc-port').value) || null,
        health_endpoint: document.getElementById('svc-health-endpoint').value || null,
        models_endpoint: document.getElementById('svc-models-endpoint').value || null,
        timeout_seconds: parseInt(document.getElementById('svc-timeout').value) || null,
        systemd_unit: document.getElementById('svc-unit').value,
        model_path: document.getElementById('svc-model').value || null,
        log_file: document.getElementById('svc-logfile').value || null,
        log_filter: document.getElementById('svc-log-filter').value || 'default',
        startup_time_seconds: parseInt(document.getElementById('svc-startup-time').value) || null,
        model_detect_pattern: document.getElementById('svc-model-detect').value || null,
        process_patterns: procPatterns ? procPatterns.split(',').map(s => s.trim()).filter(Boolean) : null,
        process_exclude_patterns: procExclude ? procExclude.split(',').map(s => s.trim()).filter(Boolean) : null,
        start_command: startCmd ? startCmd.split(/\s+/) : null,
        stop_command: stopCmd ? stopCmd.split(/\s+/) : null,
        exclusive_group: document.getElementById('svc-group').value || null,
        exec_start: document.getElementById('svc-exec-start').value || null,
    };
    return data;
}

function previewYaml() {
    const data = _collectServiceData();
    if (!data.key) { toast('Cle de service requise', true); return; }
    const y = [];
    y.push(data.key + ':');
    for (const [k, v] of Object.entries(data)) {
        if (k !== 'key' && v !== null && v !== '' && !(Array.isArray(v) && v.length === 0)) {
            if (Array.isArray(v)) {
                y.push('  ' + k + ': [' + v.map(s => '"' + s + '"').join(', ') + ']');
            } else {
                y.push('  ' + k + ': ' + (typeof v === 'string' ? '"' + v + '"' : v));
            }
        }
    }
    document.getElementById('yaml-preview').textContent = y.join('\n');
    document.getElementById('yaml-preview').style.display = 'block';
}

async function doAddService() {
    const data = _collectServiceData();
    if (!data.key) { toast('Cle de service requise', true); return; }
    const status = document.getElementById('add-status');
    status.textContent = 'Sauvegarde...';
    try {
        const resp = await fetch('/api/admin/config/service', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', ...getCsrfHeaders() },
            body: JSON.stringify(data)
        });
        const r = await resp.json();
        if (r.success) {
            toast('Service ' + data.key + ' sauve. Redemarrage en cours...');
            status.textContent = 'Sauve. Redemarrage...';
            setTimeout(() => { status.textContent = ''; switchTab('services'); }, 3000);
        } else {
            toast('Erreur: ' + (r.error || 'inconnue'), true);
            status.textContent = '';
        }
    } catch (e) {
        toast('Erreur: ' + e.message, true);
        status.textContent = '';
    }
}

async function doGenerateSystemd() {
    const data = {
        key: document.getElementById('svc-key').value || 'untitled',
        name: document.getElementById('svc-name').value || (document.getElementById('svc-key').value || 'untitled'),
        backend: document.getElementById('svc-backend').value,
        port: parseInt(document.getElementById('svc-port').value) || 8000,
        exec_start: document.getElementById('svc-exec-start').value,
        log_file: document.getElementById('svc-logfile').value || null,
    };
    try {
        const resp = await fetch('/api/admin/config/systemd/generate', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', ...getCsrfHeaders() },
            body: JSON.stringify(data)
        });
        const r = await resp.json();
        document.getElementById('systemd-preview').textContent = r.content;
        document.getElementById('systemd-preview').style.display = 'block';
    } catch (e) { toast('Erreur: ' + e.message, true); }
}

async function doInstallSystemd() {
    const data = {
        key: document.getElementById('svc-key').value || 'untitled',
        name: document.getElementById('svc-name').value || (document.getElementById('svc-key').value || 'untitled'),
        backend: document.getElementById('svc-backend').value,
        port: parseInt(document.getElementById('svc-port').value) || 8000,
        exec_start: document.getElementById('svc-exec-start').value,
        log_file: document.getElementById('svc-logfile').value || null,
    };
    try {
        const resp = await fetch('/api/admin/config/systemd/install', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', ...getCsrfHeaders() },
            body: JSON.stringify(data)
        });
        const r = await resp.json();
        if (r.success) {
            toast('Service systemd installe: ' + r.unit_name);
            document.getElementById('svc-unit').value = r.unit_name;
        } else {
            toast('Erreur installation: ' + (r.error || 'inconnue'), true);
        }
    } catch (e) { toast('Erreur: ' + e.message, true); }
}

// ===================== SERVICES TABLE =====================

async function loadServices() {
    const container = document.getElementById('services-table');
    try {
        const [svcResp, healthResp] = await Promise.all([
            fetch('/api/admin/config/services', { credentials: 'same-origin' }),
            fetch('/api/v1/services', { credentials: 'same-origin' })
        ]);
        const services = await svcResp.json();
        const health = (await healthResp.json()).services || {};
        const keys = Object.keys(services);

        if (keys.length === 0) {
            container.innerHTML = '<p style="color:#8b949e;">Aucun service defini dans config.yaml.</p>';
            return;
        }

        let html = '<table class="svc-table"><tr><th>Nom</th><th>Role</th><th>Backend</th><th>Port</th><th>Filtre</th><th>Health</th><th>Systemd</th><th></th></tr>';
        for (const k of keys) {
            const svc = services[k] || {};
            const name = svc.name || k;
            const role = svc.role || 'auxiliary';
            const backend = svc.backend || 'auto';
            const port = svc.port || '-';
            const logFilter = svc.log_filter || 'default';
            const unit = svc.systemd_unit || '-';
            const h = health[name] || '?';
            const hCls = h === 'UP' ? 'health-up' : 'health-down';
            const roleBadge = role === 'llm' ? 'badge-llm' : (role === 'project' ? 'badge-project' : 'badge-aux');
            html += `<tr>
                <td><strong>${escHtml(name)}</strong></td>
                <td><span class="${roleBadge}">${escHtml(role)}</span></td>
                <td>${escHtml(backend)}</td>
                <td>${port}</td>
                <td style="font-size:11px;color:#8b949e;">${logFilter}</td>
                <td class="${hCls}">${h}</td>
                <td>${unit}</td>
                <td>
                    <button class="btn-start btn-xs" onclick="editService('${k}')">✏</button>
                    <button class="btn-danger btn-xs" onclick="deleteService('${k}')">🗑</button>
                </td>
            </tr>`;
        }
        html += '</table>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p style="color:#f85149;">Erreur: ' + e.message + '</p>';
    }
}

async function deleteService(key) {
    if (!confirm('Supprimer le service ' + key + ' de config.yaml ?')) return;
    try {
        const resp = await fetch('/api/admin/config/service/' + key, {
            method: 'DELETE', credentials: 'same-origin',
            headers: { ...getCsrfHeaders() }
        });
        const r = await resp.json();
        if (r.success) {
            toast('Service ' + key + ' supprime. Redemarrage...');
            setTimeout(loadServices, 3000);
        } else {
            toast('Erreur suppression', true);
        }
    } catch (e) { toast('Erreur: ' + e.message, true); }
}

function editService(key) {
    fetch('/api/admin/config/services', {credentials:'same-origin'})
    .then(r => r.json())
    .then(svcs => {
        const svc = svcs[key];
        if (!svc) return;
        switchTab('add');
        _clearForm();
        const keyInput = document.getElementById('svc-key');
        keyInput.value = key;
        keyInput.readOnly = true;
        keyInput.style.opacity = '0.6';
        document.getElementById('svc-key-hint').textContent = 'Modification de ' + key + ' — les champs non modifiés sont conserves.';
        document.getElementById('svc-name').value = svc.name || key;
        document.getElementById('svc-role').value = svc.role || 'llm';
        document.getElementById('svc-backend').value = svc.backend || 'vllm';
        document.getElementById('svc-port').value = svc.port || '';
        document.getElementById('svc-url').value = svc.base_url || '';
        document.getElementById('svc-health-endpoint').value = svc.health_endpoint || '';
        document.getElementById('svc-models-endpoint').value = svc.models_endpoint || '';
        document.getElementById('svc-timeout').value = svc.timeout_seconds || '';
        document.getElementById('svc-unit').value = svc.systemd_unit || '';
        document.getElementById('svc-model').value = svc.model_path || '';
        document.getElementById('svc-logfile').value = svc.log_file || '';
        document.getElementById('svc-log-filter').value = svc.log_filter || 'default';
        document.getElementById('svc-startup-time').value = svc.startup_time_seconds || '';
        document.getElementById('svc-model-detect').value = svc.model_detect_pattern || '';
        document.getElementById('svc-process-patterns').value = (svc.process_patterns || []).join(', ');
        document.getElementById('svc-process-exclude').value = (svc.process_exclude_patterns || []).join(', ');
        const startCmd = svc.start_command || [];
        const stopCmd = svc.stop_command || [];
        document.getElementById('svc-start-command').value = startCmd.join(' ');
        document.getElementById('svc-stop-command').value = stopCmd.join(' ');
        document.getElementById('svc-group').value = svc.exclusive_group || '';
        // Set exec_start from config data first
        if (svc.exec_start) {
            document.getElementById('svc-exec-start').value = svc.exec_start;
        }
        // Then try to load actual ExecStart from systemd .service file (overrides config)
        const unit = svc.systemd_unit;
        if (unit) {
            fetch('/api/admin/config/systemd/read?unit=' + encodeURIComponent(unit), {credentials:'same-origin'})
            .then(r => r.json())
            .then(data => {
                if (data.exec_start) {
                    document.getElementById('svc-exec-start').value = data.exec_start;
                }
            }).catch(() => {});
        }
    });
}

// Init
document.getElementById('svc-backend').addEventListener('change', onBackendChange);
