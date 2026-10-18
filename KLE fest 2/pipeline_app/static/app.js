/* Moolya front-end logic.
   Works with the Moolya index.html and style.css, and talks to the same
   backend: POST /api/estimate (SSE stream) and POST /api/chat. */
(() => {
  'use strict';

  /* =========================================================
     Config
     ========================================================= */
  const CONFIG = {
    endpoints: { estimate: '/api/estimate', chat: '/api/chat' },
    maxBytes: 20 * 1024 * 1024,
    mobileBreakpoint: 960,
    files: {
      image: { types: ['image/png', 'image/jpeg', 'image/webp'], label: 'PNG, JPG or WEBP image' },
      pdf: { types: ['application/pdf'], label: 'PDF document' },
    },
    stageIdle: {
      gemini: 'Starting analysis...',
      hardware: 'Waits for the brief',
      software: 'Waits for the brief',
      nemotron: 'Waits for both agents',
      prediction: 'Waits for both agents',
    },
    stageAlias: { gemini_pred: 'prediction' },
    chatGreeting:
      'Run an estimate first, then ask about component prices, team cost, the timeline or any line in the breakdown.',
    chatReady: 'Your estimate is ready. Ask about components, prices, sources, the team or the timeline.',
  };

  /* =========================================================
     State and element lookup
     ========================================================= */
  const $ = (id) => document.getElementById(id);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const state = {
    mode: 'text',
    files: { image: null, pdf: null },
    previewUrl: null,
    fileError: '',
    sessionId: null,
    hw: null,
    sw: null,
    running: false,
    gotDone: false,
    chatBusy: false,
  };

  const els = {
    form: $('composer'),
    text: $('project-text'),
    run: $('analyse-btn'),
    hint: $('input-hint'),
    error: $('run-error'),
    results: $('results'),
    empty: $('empty'),
    dialog: $('sources-dialog'),
    chat: $('chat'),
    chatLog: $('chat-log'),
    chatInput: $('chat-input'),
    chatSend: $('chat-send'),
    chatSuggest: $('chat-suggest'),
    scrim: $('scrim'),
    askBtn: $('ask-btn'),
    routeList: document.querySelector('.route-list'),
  };

  /* =========================================================
     Helpers
     ========================================================= */
  const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC_MAP[c]);

  const plural = (n, one, many) => (n === 1 ? one : many);

  function safeUrl(u) {
    try {
      const x = new URL(u);
      return x.protocol === 'http:' || x.protocol === 'https:' ? x.href : '';
    } catch (e) {
      return '';
    }
  }

  function fmt(n) {
    if ((!n && n !== 0) || Number.isNaN(Number(n))) return '-';
    return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
  }

  function fmtRange(min, max) {
    if (!min && !max) return '-';
    if (!max || min === max) return fmt(min);
    return fmt(min) + ' to ' + fmt(max);
  }

  function fmtSize(bytes) {
    return bytes < 1024 * 1024
      ? Math.max(1, Math.round(bytes / 1024)) + ' KB'
      : (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function midpoint(range) {
    const a = Number((range || {}).min) || 0;
    const b = Number((range || {}).max) || 0;
    return a && b ? (a + b) / 2 : a || b;
  }

  const sentenceCase = (s) => {
    s = String(s || '');
    return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : '';
  };

  /* =========================================================
     Brief input: modes, files, validation
     ========================================================= */
  function setMode(mode) {
    state.mode = mode;
    state.fileError = '';
    document.querySelectorAll('.mode').forEach((b) => {
      const on = b.dataset.mode === mode;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-selected', String(on));
      b.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll('.pane').forEach((p) => {
      const on = p.id === 'pane-' + mode;
      p.classList.toggle('is-active', on);
      p.hidden = !on;
    });
    refreshInput();
  }

  function inputIsReady() {
    return state.mode === 'text' ? els.text.value.trim().length > 0 : !!state.files[state.mode];
  }

  function refreshInput() {
    let msg;
    if (state.mode === 'text') {
      const t = els.text.value.trim();
      const words = t ? t.split(/\s+/).length : 0;
      msg = words ? `${words} ${plural(words, 'word', 'words')} ready.` : 'Describe the project to begin.';
    } else {
      const f = state.files[state.mode];
      msg = f ? `${f.name} is ready.` : state.mode === 'image' ? 'Add an image to begin.' : 'Add a PDF to begin.';
    }
    if (state.fileError) msg = state.fileError;
    els.hint.textContent = msg;
    els.hint.classList.toggle('is-error', !!state.fileError);
    els.run.disabled = !inputIsReady() || state.running;
  }

  function rejectFile(kind, message) {
    state.fileError = message;
    $(kind + '-input').value = '';
    refreshInput();
  }

  function setFile(kind, file) {
    const rule = CONFIG.files[kind];
    const typeOk = rule.types.includes(file.type) || (kind === 'pdf' && /\.pdf$/i.test(file.name));
    if (!typeOk) return rejectFile(kind, `That file is not a ${rule.label}.`);
    if (file.size > CONFIG.maxBytes) {
      return rejectFile(kind, `That file is ${fmtSize(file.size)}. The limit is 20 MB.`);
    }

    state.fileError = '';
    state.files[kind] = file;
    $(kind + '-prompt').hidden = true;
    $(kind + '-chip').hidden = false;
    $(kind + '-name').textContent = file.name;
    $(kind + '-size').textContent = fmtSize(file.size);

    if (kind === 'image') {
      if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = URL.createObjectURL(file);
      $('image-preview').src = state.previewUrl;
    }
    refreshInput();
  }

  function clearFile(kind) {
    state.files[kind] = null;
    state.fileError = '';
    $(kind + '-input').value = '';
    $(kind + '-chip').hidden = true;
    $(kind + '-prompt').hidden = false;
    if (kind === 'image' && state.previewUrl) {
      URL.revokeObjectURL(state.previewUrl);
      state.previewUrl = null;
      $('image-preview').removeAttribute('src');
    }
    refreshInput();
  }

  function bindDropzone(kind) {
    const zone = $(kind + '-dropzone');
    const input = $(kind + '-input');
    zone.addEventListener('dragover', (e) => {
      e.preventDefault();
      zone.classList.add('is-over');
    });
    ['dragleave', 'dragend'].forEach((t) => zone.addEventListener(t, () => zone.classList.remove('is-over')));
    zone.addEventListener('drop', (e) => {
      e.preventDefault();
      zone.classList.remove('is-over');
      const f = e.dataTransfer.files[0];
      if (f) setFile(kind, f);
    });
    input.addEventListener('change', () => {
      if (input.files[0]) setFile(kind, input.files[0]);
    });
  }

  /* =========================================================
     Progress route
     ========================================================= */
  function setStage(name, status, msg) {
    const el = $('stage-' + name);
    const m = $('msg-' + name);
    if (!el || !m) return;
    el.className = 'station is-' + status;
    m.textContent = msg || '';
  }

  function resetRoute() {
    Object.keys(CONFIG.stageIdle).forEach((s) => setStage(s, 'waiting', CONFIG.stageIdle[s]));
    ['gemini', 'hardware', 'software', 'nemotron', 'prediction'].forEach((s) => {
      const wrap = $('output-wrap-' + s);
      const output = $('output-' + s);
      wrap.hidden = true;
      output.textContent = '';
      wrap.open = false;
    });
    $('card-hw-sources').hidden = true;
    $('card-sw-sources').hidden = true;
  }

  function showStageOutput(name, value) {
    if (value === undefined || value === null || value === '') return;
    const wrap = $('output-wrap-' + name);
    const output = $('output-' + name);
    if (!wrap || !output) return;
    output.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    wrap.hidden = false;
  }

  // Marks whichever step was in flight as failed (falls back to the first step).
  function failActiveStage(message) {
    const active = els.routeList.querySelector('.station.is-running');
    const name = active ? active.id.replace('stage-', '') : 'gemini';
    setStage(name, 'error', message);
  }

  function toggleSources(kind, count) {
    $(kind + '-source-count').textContent = count;
    $('btn-' + kind + '-all-sources').hidden = count === 0;
    $('card-' + kind + '-sources').hidden = count === 0;
  }

  function showError(msg) {
    els.error.textContent = msg;
    els.error.hidden = false;
  }

  /* =========================================================
     Estimate run: POST then read the SSE stream
     ========================================================= */
  function buildPayload() {
    const fd = new FormData();
    fd.append('mode', state.mode);
    if (state.mode === 'text') fd.append('text', els.text.value.trim());
    else if (state.mode === 'image') fd.append('image', state.files.image);
    else if (state.mode === 'pdf') fd.append('pdf', state.files.pdf);
    return fd;
  }

  async function startPipeline() {
    if (state.running || !inputIsReady()) return;
    const payload = buildPayload();

    state.running = true;
    state.gotDone = false;
    state.sessionId = null;
    els.run.textContent = 'Estimating...';
    els.error.hidden = true;
    els.results.hidden = true;
    els.empty.hidden = false;
    els.routeList.setAttribute('aria-busy', 'true');
    resetRoute();
    resetChat();
    refreshInput();

    try {
      const res = await fetch(CONFIG.endpoints.estimate, { method: 'POST', body: payload });
      if (!res.ok || !res.body) throw new Error('Server responded with status ' + res.status);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        parts.forEach(handleChunk);
      }
      if (buffer.trim()) handleChunk(buffer);

      if (!state.gotDone) throw new Error('The connection closed before the estimate finished.');
    } catch (err) {
      failActiveStage('Stopped: ' + err.message);
      if (els.error.hidden) showError('The estimate could not be completed. ' + err.message);
    } finally {
      state.running = false;
      els.run.textContent = 'Estimate cost';
      els.routeList.setAttribute('aria-busy', 'false');
      refreshInput();
    }
  }

  function handleChunk(part) {
    let event = 'message';
    const data = [];
    part
      .replace(/\r/g, '')
      .split('\n')
      .forEach((line) => {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trim());
      });
    if (!data.length) return;
    try {
      handleEvent(event, JSON.parse(data.join('\n')));
    } catch (e) {
      console.error('Could not handle stream event:', e);
    }
  }

  function handleEvent(event, data) {
    if (event === 'stage') return handleStage(data);
    if (event === 'done') return handleDone(data);
  }

  function handleStage(data) {
    const id = CONFIG.stageAlias[data.stage] || data.stage;
    setStage(id, data.status, data.message);
    const finished = data.status === 'done' && data.data;

    if (finished && data.stage === 'gemini') {
      const providerLabel = data.provider || 'unknown';
      $('stage-gemini').querySelector('.station-tool').textContent = providerLabel;
      const sections = [
        `Provider: ${providerLabel}`,
        'Raw provider response:',
        data.raw_output || '(No raw provider text was returned.)',
        'Normalized requirements sent to the agents:',
        JSON.stringify(data.data, null, 2),
      ];
      showStageOutput('gemini', sections.join('\n\n'));
    }
    if (finished && data.stage === 'hardware') {
      showStageOutput('hardware', data.raw_output || data.data);
    }
    if (finished && data.stage === 'software') {
      const localOutput = data.raw_output || '(No local model prediction output.)';
      showStageOutput(
        'software',
        `Exact local model prediction:\n${localOutput}\n\nFull software estimate:\n${JSON.stringify(data.data, null, 2)}`
      );
    }
    if (finished && data.stage === 'nemotron') {
      showStageOutput('nemotron', data.data);
    }
    if (finished && data.stage === 'prediction') {
      showStageOutput('prediction', data.data);
    }

    if (data.stage === 'hardware' && finished) {
      state.hw = data.data;
      toggleSources('hw', (state.hw.all_sources || []).length);
    }
    if (data.stage === 'software' && finished) {
      state.sw = data.data;
      toggleSources('sw', (state.sw.all_sources || []).length);
    }
    if (id === 'prediction' && finished) renderPrediction(data.data);
  }

  function handleDone(data) {
    state.gotDone = true;
    state.sessionId = data.session_id || state.sessionId;

    if (data.error) {
      showError(typeof data.error === 'string' ? data.error : 'The estimate could not be completed.');
      return;
    }

    state.hw = data.hardware || {};
    state.sw = data.software || {};
    if (data.nemotron) showStageOutput('nemotron', data.nemotron);
    renderAll(data);

    els.empty.hidden = true;
    els.results.hidden = false;
    els.chatSuggest.hidden = false;
    appendChat('bot', CONFIG.chatReady);

    if (window.innerWidth <= CONFIG.mobileBreakpoint) {
      els.results.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    }
  }

  /* =========================================================
     Rendering
     ========================================================= */
  function renderRange(tc) {
    $('cost-opt').textContent = fmt(tc.optimistic);
    $('cost-likely').textContent = fmt(tc.likely);
    $('cost-pess').textContent = fmt(tc.pessimistic);

    // Position of "likely" between the low and high case, kept inside the bar.
    const lo = Number(tc.optimistic);
    const hi = Number(tc.pessimistic);
    const mid = Number(tc.likely);
    let pct = 50;
    if (hi > lo && mid >= lo) pct = Math.min(96, Math.max(4, ((mid - lo) / (hi - lo)) * 100));
    $('scale-lo').style.width = pct + '%';
    $('scale-mark').style.left = pct + '%';
  }

  function renderBreakdown(p) {
    const hw = p.hardware_cost_inr || {};
    const dev = p.software_dev_cost_inr || {};
    const lic = p.licence_cost_inr || {};
    $('bk-hw').textContent = fmtRange(hw.min, hw.max);
    $('bk-dev').textContent = fmtRange(dev.min, dev.max);
    $('bk-lic').textContent = fmtRange(lic.min, lic.max);

    const parts = [midpoint(hw), midpoint(dev), midpoint(lic)];
    const sum = parts.reduce((a, b) => a + b, 0);
    ['seg-hw', 'seg-dev', 'seg-lic'].forEach((id, i) => {
      $(id).style.width = sum > 0 ? (parts[i] / sum) * 100 + '%' : '0';
    });
  }

  function renderFlags(p) {
    const flags = [...(p.duplicates_flagged || []), ...(p.missing_specs || [])];
    $('flags-section').hidden = flags.length === 0;
    $('flags-wrap').innerHTML = flags.length ? '<ul>' + flags.map((f) => `<li>${esc(f)}</li>`).join('') + '</ul>' : '';
  }

  function renderPrediction(p) {
    renderRange(p.total_cost_inr || {});
    renderBreakdown(p);
    renderFlags(p);
    $('cost-summary').textContent = p.summary || '';

    const eff = p.effort_months || {};
    $('bk-months').textContent = eff.likely ? `${eff.low} to ${eff.high} months, likely about ${eff.likely}` : '-';
    $('bk-conf').textContent = sentenceCase(p.confidence) || '-';
  }

  function sourceButton(type, idx, count) {
    return count > 0
      ? `<button type="button" class="src-btn" data-item-sources="${type}:${idx}">${count} ${plural(count, 'link', 'links')}</button>`
      : '<span class="block-note">None</span>';
  }

  const sourceCount = (it) => (it.sources || []).length || it.source_count || 0;

  function renderHardware(hw) {
    const wrap = $('hw-table-wrap');
    const items = hw.items || [];
    toggleSources('hw', (hw.all_sources || []).length);

    if (!items.length) {
      wrap.innerHTML = '<p class="none">No hardware components required.</p>';
      return;
    }

    const rows = items
      .map((it, idx) => {
        const models = (it.suggested_models || [])
          .map((m) => `<span class="tag tag-model">${esc(((m.maker || '') + ' ' + (m.model || '')).trim())}</span>`)
          .join('');
        const unitPrice = it.unit_price_inr ? fmt(it.unit_price_inr) : (it.price_str || '-');
        const lineTotal = it.line_total_inr ? fmt(it.line_total_inr) : '-';
        const seller = esc(it.seller_source || 'Electronics Supplier');
        const buyLink = it.product_url
          ? `<a class="src-btn" href="${esc(it.product_url)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;display:inline-block;">Buy / View</a>`
          : sourceButton('hardware', idx, sourceCount(it));

        return `<tr>
          <td>
            <strong>${esc(it.name)}</strong>
            ${it.spec ? `<small>${esc(it.spec)}</small>` : ''}
          </td>
          <td>${it.quantity || 1}</td>
          <td>${models || '-'}</td>
          <td><span class="tag tag-plain">${seller}</span></td>
          <td>${unitPrice}</td>
          <td><strong>${lineTotal}</strong></td>
          <td>${buyLink}</td>
        </tr>`;
      })
      .join('');

    const t = hw.total || {};
    const foot =
      t.likely || t.min || t.max
        ? `<tfoot>
            <tr>
              <td colspan="4"><strong>Total Hardware Cost</strong></td>
              <td colspan="3" style="text-align:right;">
                <strong>${fmt(t.likely)}</strong>
                <small style="color:var(--ink-3);display:block;">Range: ${fmtRange(t.min, t.max)}</small>
              </td>
            </tr>
          </tfoot>`
        : '';

    wrap.innerHTML = `<table>
      <thead>
        <tr>
          <th>Component & Spec</th>
          <th>Qty</th>
          <th>Suggested Models</th>
          <th>Seller Source</th>
          <th>Unit Price</th>
          <th>Line Total</th>
          <th>Link / Sources</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      ${foot}
    </table>`;
  }

  function renderSoftware(sw) {
    const wrap = $('sw-table-wrap');
    toggleSources('sw', (sw.all_sources || []).length);

    const payload = sw.software_payload || {};
    const baseline = sw.baseline_estimate || {};
    const labor = sw.labor_breakdown || [];
    const bom = sw.bom_breakdown || [];
    const mc = sw.monte_carlo_uncertainty || null;
    const ml = sw.ml_prediction || null;
    const analogy = sw.analogy_estimate || null;

    if (!labor.length && !sw.items) {
      wrap.innerHTML = '<p class="none">No software requirements generated.</p>';
      return;
    }

    // Key Metrics Highlights
    const projName = esc(payload.project_name || 'Software Development Project');
    const baseTotal = baseline.total_project_cost ? fmt(baseline.total_project_cost) : '-';
    const mcP50 = mc && mc.simulated_median_p50 ? fmt(mc.simulated_median_p50) : baseTotal;
    const mcP10 = mc && mc.p10 ? fmt(mc.p10) : '-';
    const mcP90 = mc && mc.p90 ? fmt(mc.p90) : '-';
    const mlHours = ml && ml.prediction ? `${ml.prediction.toLocaleString('en-IN', {maximumFractionDigits: 1})} hrs` : '-';
    const mlCost = ml && ml.calculated_ml_cost ? fmt(ml.calculated_ml_cost) : '-';
    const mlModelVer = ml ? esc(`${ml.algorithm || 'XGBoost'} (${ml.dataset_version || 'Desharnais'})`) : 'Trained ML Model';
    const timeline = payload.ml_features && payload.ml_features.Length ? `${payload.ml_features.Length} months` : '6 months';

    let html = `
      <div style="margin-bottom: 22px; padding: 18px 20px; background: var(--paper-2); border: 1px solid var(--line); border-radius: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 14px;">
          <h4 style="margin: 0; font-size: 16px; font-weight: 700; color: var(--indigo);">${projName}</h4>
          <span class="tag tag-build" style="margin:0;">Target: ${esc(payload.target_metric || 'Effort')}</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px 20px;">
          <div>
            <div style="font-size: 12px; color: var(--ink-3); text-transform: uppercase; font-weight: 600;">Baseline Dev Cost</div>
            <div style="font-size: 20px; font-weight: 700; color: var(--ink);">${baseTotal}</div>
            <small style="color:var(--ink-3);display:block;">Direct Labor + BOM + Rules</small>
          </div>
          <div>
            <div style="font-size: 12px; color: var(--ink-3); text-transform: uppercase; font-weight: 600;">Monte Carlo P50 Expected</div>
            <div style="font-size: 20px; font-weight: 700; color: var(--moss);">${mcP50}</div>
            <small style="color:var(--ink-3);display:block;">P10: ${mcP10} – P90: ${mcP90}</small>
          </div>
          <div>
            <div style="font-size: 12px; color: var(--ink-3); text-transform: uppercase; font-weight: 600;">ML Effort Prediction</div>
            <div style="font-size: 20px; font-weight: 700; color: var(--indigo);">${mlHours}</div>
            <small style="color:var(--ink-3);display:block;">${mlModelVer} (~${mlCost})</small>
          </div>
          <div>
            <div style="font-size: 12px; color: var(--ink-3); text-transform: uppercase; font-weight: 600;">Estimated Timeline</div>
            <div style="font-size: 20px; font-weight: 700; color: var(--ink);">${timeline}</div>
            <small style="color:var(--ink-3);display:block;">Effort Model Duration</small>
          </div>
        </div>
      </div>
    `;

    // Itemised Labor Table
    if (labor.length) {
      const laborRows = labor.map((l) => `
        <tr>
          <td><strong>${esc(l.role_name)}</strong></td>
          <td>${l.personnel_count || 1}</td>
          <td>${l.hours} hrs</td>
          <td>${fmt(l.hourly_rate)} / hr</td>
          <td style="text-align:right;"><strong>${fmt(l.line_total)}</strong></td>
        </tr>
      `).join('');

      const laborTot = baseline.direct_labor_cost ? fmt(baseline.direct_labor_cost) : '-';
      html += `
        <h4 style="margin: 20px 0 10px; font-size: 14.5px; font-weight: 650; color: var(--ink-2);">Software & Engineering Team Allocation</h4>
        <table style="margin-bottom: 24px;">
          <thead>
            <tr>
              <th>Role</th>
              <th>Headcount</th>
              <th>Hours / Person</th>
              <th>Hourly Rate</th>
              <th style="text-align:right;">Direct Labor Cost</th>
            </tr>
          </thead>
          <tbody>${laborRows}</tbody>
          <tfoot>
            <tr>
              <td colspan="4">Total Direct Labor</td>
              <td style="text-align:right;">${laborTot}</td>
            </tr>
          </tfoot>
        </table>
      `;
    }

    // Software BOM & Tool Licenses Table
    if (bom.length) {
      const bomRows = bom.map((b) => `
        <tr>
          <td><strong>${esc(b.item_name)}</strong>${b.source ? `<small>${esc(b.source)}</small>` : ''}</td>
          <td><span class="tag tag-plain">${esc(b.category || 'software')}</span></td>
          <td>${b.quantity || 1} ${esc(b.unit || 'license')}</td>
          <td>${fmt(b.unit_price)}</td>
          <td style="text-align:right;"><strong>${fmt(b.line_total)}</strong></td>
        </tr>
      `).join('');

      const bomTot = baseline.direct_materials_cost ? fmt(baseline.direct_materials_cost) : '-';
      html += `
        <h4 style="margin: 20px 0 10px; font-size: 14.5px; font-weight: 650; color: var(--ink-2);">Software Tooling, Infrastructure & Licenses (BOM)</h4>
        <table style="margin-bottom: 24px;">
          <thead>
            <tr>
              <th>Tool / License</th>
              <th>Category</th>
              <th>Quantity</th>
              <th>Unit Price</th>
              <th style="text-align:right;">Line Total</th>
            </tr>
          </thead>
          <tbody>${bomRows}</tbody>
          <tfoot>
            <tr>
              <td colspan="4">Total Tooling & Licenses</td>
              <td style="text-align:right;">${bomTot}</td>
            </tr>
          </tfoot>
        </table>
      `;
    }

    // Overheads, Contingency & Taxes Breakdown
    const rules = payload.rules || {};
    html += `
      <div style="margin: 20px 0 24px; padding: 16px 20px; background: var(--paper); border: 1px solid var(--line); border-radius: 9px;">
        <h4 style="margin: 0 0 12px; font-size: 14px; font-weight: 650; color: var(--ink-2);">Cost Markups & Statutory Rates</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px 18px; font-size: 13.5px;">
          <div><span style="color:var(--ink-3);">Direct Subtotal:</span> <strong>${fmt(baseline.direct_total_cost)}</strong></div>
          <div><span style="color:var(--ink-3);">Overhead (${rules.overhead_percentage || 15}%):</span> <strong>${fmt(baseline.overhead_amount)}</strong></div>
          <div><span style="color:var(--ink-3);">Contingency (${rules.contingency_percentage || 10}%):</span> <strong>${fmt(baseline.contingency_amount)}</strong></div>
          <div><span style="color:var(--ink-3);">Taxes / GST (${rules.tax_percentage || 18}%):</span> <strong>${fmt(baseline.tax_amount)}</strong></div>
        </div>
      </div>
    `;

    // Historical Analogies (Desharnais Dataset)
    if (analogy && analogy.similar_projects && analogy.similar_projects.length) {
      const projRows = analogy.similar_projects.map((p) => `
        <tr>
          <td>#${p.project_index}</td>
          <td><span class="tag tag-build">${p.similarity_score_pct.toFixed(1)}%</span></td>
          <td>${p.distance.toFixed(2)}</td>
          <td><strong>${p.actual_target_value.toLocaleString('en-IN')} hrs</strong></td>
          <td>${esc(p.features ? Object.entries(p.features).slice(0, 3).map(([k,v]) => `${k}:${v}`).join(', ') : '-')}</td>
        </tr>
      `).join('');

      html += `
        <h4 style="margin: 20px 0 10px; font-size: 14.5px; font-weight: 650; color: var(--ink-2);">Historical Project Analogies (Desharnais Software Projects)</h4>
        <p style="font-size: 13px; color: var(--ink-3); margin-bottom: 8px;">Top ${analogy.similar_projects.length} most similar historical projects from the calibrated repository (Average similarity: ${analogy.mean_similarity_pct.toFixed(1)}%):</p>
        <table style="margin-bottom: 24px;">
          <thead>
            <tr>
              <th>Historical ID</th>
              <th>Similarity</th>
              <th>Distance</th>
              <th>Actual Historical Effort</th>
              <th>Key Historical Features</th>
            </tr>
          </thead>
          <tbody>${projRows}</tbody>
        </table>
      `;
    }

    // Monte Carlo Uncertainty Simulation Summary
    if (mc && mc.iterations) {
      const drivers = (mc.top_cost_drivers || []).slice(0, 3).map(d => esc(d.name)).join(', ');
      html += `
        <div style="padding: 16px 20px; background: var(--moss-tint); border: 1px solid var(--moss-soft); border-radius: 9px; font-size: 13.5px; color: var(--ink);">
          <div style="font-weight: 700; color: var(--moss); margin-bottom: 6px;">Monte Carlo Risk Simulation (${mc.iterations.toLocaleString('en-IN')} Iterations, Seed: ${mc.random_seed})</div>
          <div>Simulated Median P50: <strong>${fmt(mc.simulated_median_p50)}</strong> | 80% Confidence Interval: <strong>${fmt(mc.p10)} to ${fmt(mc.p90)}</strong> | Std Dev: <strong>${fmt(mc.std_dev)}</strong></div>
          ${drivers ? `<div style="margin-top: 4px; color: var(--ink-2); font-size: 12.5px;">Primary Risk Drivers: ${drivers}</div>` : ''}
        </div>
      `;
    }

    wrap.innerHTML = html;
  }

  function renderTeam(team) {
    const wrap = $('team-wrap');
    if (!team.length) {
      wrap.innerHTML = '<p class="none">No specific engineering roles suggested.</p>';
      return;
    }
    wrap.innerHTML =
      '<ul class="team">' +
      team.map((r) => `<li><strong>${esc(r.role)}</strong><span>${esc(r.reason)}</span></li>`).join('') +
      '</ul>';
  }

  function renderAll(data) {
    renderHardware(data.hardware || {});
    renderSoftware(data.software || {});
    renderTeam((data.gemini || {}).team || []);

    const p = data.prediction;
    if (p && !p.error) renderPrediction(p);
    else if (p && p.error) $('cost-summary').textContent = 'The total forecast failed: ' + p.error;
  }

  /* =========================================================
     Sources dialog
     ========================================================= */
  function sourceRow(s) {
    const url = safeUrl(s.url);
    let host = '';
    try {
      host = new URL(url).hostname.replace(/^www\./, '');
    } catch (e) {
      /* no valid host */
    }
    const label = esc(s.title || s.url || 'Untitled source');
    const link = url
      ? `<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
      : `<span class="source-link">${label}</span>`;

    return `<div class="source">
      <div class="source-meta">
        ${s.item ? `<span class="source-chip item">${esc(s.item)}</span>` : ''}
        ${host ? `<span class="source-chip">${esc(host)}</span>` : ''}
      </div>
      ${link}
      ${s.snippet ? `<p class="source-snippet">${esc(s.snippet)}</p>` : ''}
      ${url ? `<p class="source-url">${esc(url)}</p>` : ''}
    </div>`;
  }

  function openSources(title, list) {
    $('modal-title').textContent = `${title} (${list.length})`;
    $('modal-content').innerHTML = list.length
      ? list.map(sourceRow).join('')
      : '<p class="none" style="padding:24px 0">No external links found for this item.</p>';
    els.dialog.showModal();
  }

  function openAllSources(type) {
    const isHw = type === 'hardware';
    const data = isHw ? state.hw : state.sw;
    openSources(isHw ? 'Hardware sources' : 'Software sources', (data && data.all_sources) || []);
  }

  function openItemSources(type, idx) {
    const data = type === 'hardware' ? state.hw : state.sw;
    const item = data && data.items ? data.items[idx] : null;
    if (!item) return;
    openSources('Sources for ' + item.name, (item.sources || []).map((s) => ({ ...s, item: item.name })));
  }

  /* =========================================================
     Chat drawer
     ========================================================= */
  function openChat() {
    els.chat.classList.add('is-open');
    els.chat.removeAttribute('inert');
    els.chat.setAttribute('aria-hidden', 'false');
    els.scrim.hidden = false;
    els.chatInput.focus();
  }

  function closeChat() {
    els.chat.classList.remove('is-open');
    els.chat.setAttribute('inert', '');
    els.chat.setAttribute('aria-hidden', 'true');
    els.scrim.hidden = true;
    els.askBtn.focus();
  }

  function appendChat(cls, text) {
    const el = document.createElement('div');
    el.className = 'msg ' + cls;
    el.textContent = text;
    els.chatLog.appendChild(el);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
    return el;
  }

  function resetChat() {
    els.chatLog.innerHTML = '';
    appendChat('bot', CONFIG.chatGreeting);
    els.chatSuggest.hidden = true;
  }

  async function sendChat(text) {
    if (state.chatBusy) return;
    const msg = String(text ?? els.chatInput.value).trim();
    if (!msg) return;

    state.chatBusy = true;
    els.chatSend.disabled = true;
    els.chatInput.value = '';
    appendChat('user', msg);
    const pending = appendChat('bot thinking', 'Thinking...');

    try {
      const res = await fetch(CONFIG.endpoints.chat, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: state.sessionId || '', message: msg }),
      });
      const d = await res.json();
      pending.className = 'msg bot';
      pending.textContent = d.reply || d.error || 'No response.';
    } catch (e) {
      pending.className = 'msg bot';
      pending.textContent = 'Error: ' + e.message;
    } finally {
      state.chatBusy = false;
      els.chatSend.disabled = false;
      els.chatLog.scrollTop = els.chatLog.scrollHeight;
    }
  }

  /* =========================================================
     Wiring
     ========================================================= */
  const modeButtons = Array.from(document.querySelectorAll('.mode'));
  modeButtons.forEach((btn, i) => {
    btn.addEventListener('click', () => setMode(btn.dataset.mode));
    btn.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const step = e.key === 'ArrowRight' ? 1 : modeButtons.length - 1;
      const next = modeButtons[(i + step) % modeButtons.length];
      next.focus();
      setMode(next.dataset.mode);
    });
  });

  els.text.addEventListener('input', refreshInput);
  els.text.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') startPipeline();
  });
  els.form.addEventListener('submit', (e) => {
    e.preventDefault();
    startPipeline();
  });

  bindDropzone('image');
  bindDropzone('pdf');

  // One delegated click handler for every data-* action button.
  document.addEventListener('click', (e) => {
    const clear = e.target.closest('[data-clear]');
    if (clear) {
      e.preventDefault();
      e.stopPropagation();
      return clearFile(clear.dataset.clear);
    }

    const all = e.target.closest('[data-sources]');
    if (all) return openAllSources(all.dataset.sources);

    const item = e.target.closest('[data-item-sources]');
    if (item) {
      const [type, idx] = item.dataset.itemSources.split(':');
      return openItemSources(type, Number(idx));
    }

    const ask = e.target.closest('[data-ask]');
    if (ask) {
      openChat();
      sendChat(ask.dataset.ask);
    }
  });

  els.dialog.addEventListener('click', (e) => {
    if (e.target.closest('[data-close]')) return els.dialog.close();
    if (e.target === els.dialog) {
      const r = els.dialog.getBoundingClientRect();
      const outside = e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      if (outside) els.dialog.close();
    }
  });

  els.askBtn.addEventListener('click', openChat);
  $('chat-close').addEventListener('click', closeChat);
  els.scrim.addEventListener('click', closeChat);
  $('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    sendChat();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && els.chat.classList.contains('is-open')) closeChat();
  });

  setMode('text');
})();