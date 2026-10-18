(() => {
  'use strict';

  /* ---------- Config and state ---------- */
  const MAX_BYTES = 20 * 1024 * 1024;
  const FILE_RULES = {
    image: { types: ['image/png', 'image/jpeg', 'image/webp'], label: 'PNG, JPG or WEBP image' },
    pdf: { types: ['application/pdf'], label: 'PDF document' },
  };
  const STAGES = ['gemini', 'hardware', 'software', 'prediction'];
  const IDLE_MSG = {
    gemini: 'Starting analysis...',
    hardware: 'Waits for the brief',
    software: 'Waits for the brief',
    prediction: 'Waits for both agents',
  };

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
    scrim: $('scrim'),
  };

  /* ---------- Helpers ---------- */
  const esc = (s) =>
    String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

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

  const midpoint = (r) => {
    r = r || {};
    const a = Number(r.min) || 0;
    const b = Number(r.max) || 0;
    return a && b ? (a + b) / 2 : a || b;
  };

  const plural = (n, one, many) => (n === 1 ? one : many);

  /* ---------- Input modes ---------- */
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

  function refreshInput() {
    let ready = false;
    let msg = '';
    if (state.mode === 'text') {
      const t = els.text.value.trim();
      const words = t ? t.split(/\s+/).length : 0;
      ready = words > 0;
      msg = ready ? `${words} ${plural(words, 'word', 'words')} ready.` : 'Describe the project to begin.';
    } else {
      const f = state.files[state.mode];
      ready = !!f;
      msg = f ? `${f.name} is ready.` : state.mode === 'image' ? 'Add an image to begin.' : 'Add a PDF to begin.';
    }
    if (state.fileError) msg = state.fileError;
    els.hint.textContent = msg;
    els.hint.classList.toggle('is-error', !!state.fileError);
    els.run.disabled = !ready || state.running;
  }

  function setFile(kind, file) {
    const rule = FILE_RULES[kind];
    const okType = rule.types.includes(file.type) || (kind === 'pdf' && file.name.toLowerCase().endsWith('.pdf'));
    if (!okType) {
      state.fileError = `That file is not a ${rule.label}.`;
      $(kind + '-input').value = '';
      return refreshInput();
    }
    if (file.size > MAX_BYTES) {
      state.fileError = `That file is ${fmtSize(file.size)}. The limit is 20 MB.`;
      $(kind + '-input').value = '';
      return refreshInput();
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

  /* ---------- Pipeline route ---------- */
  function setStage(name, status, msg) {
    const el = $('stage-' + name);
    const m = $('msg-' + name);
    if (!el || !m) return;
    el.className = 'station is-' + status;
    m.textContent = msg || '';
  }

  function resetRoute() {
    STAGES.forEach((s) => setStage(s, 'waiting', IDLE_MSG[s]));
    $('card-hw-sources').hidden = true;
    $('card-sw-sources').hidden = true;
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

  /* ---------- Run the estimate (SSE over fetch) ---------- */
  async function startPipeline() {
    if (state.running) return;
    const fd = new FormData();
    fd.append('mode', state.mode);

    if (state.mode === 'text') {
      const t = els.text.value.trim();
      if (!t) return;
      fd.append('text', t);
    } else if (state.mode === 'image') {
      if (!state.files.image) return;
      fd.append('image', state.files.image);
    } else if (state.mode === 'pdf') {
      if (!state.files.pdf) return;
      fd.append('pdf', state.files.pdf);
    } else {
      return;
    }

    state.running = true;
    els.run.textContent = 'Estimating...';
    els.error.hidden = true;
    els.results.hidden = true;
    els.empty.hidden = false;
    resetRoute();
    refreshInput();

    try {
      const res = await fetch('/api/estimate', { method: 'POST', body: fd });
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
    } catch (err) {
      setStage('gemini', 'error', 'Request failed: ' + err.message);
      showError('The estimate could not be completed. ' + err.message);
    } finally {
      state.running = false;
      els.run.textContent = 'Estimate cost';
      refreshInput();
    }
  }

  function handleChunk(part) {
    let event = 'message';
    const data = [];
    part.replace(/\r/g, '').split('\n').forEach((l) => {
      if (l.startsWith('event:')) event = l.slice(6).trim();
      else if (l.startsWith('data:')) data.push(l.slice(5).trim());
    });
    if (!data.length) return;
    try {
      handleEvent(event, JSON.parse(data.join('\n')));
    } catch (e) {
      console.error('Could not handle stream event', e);
    }
  }

  function handleEvent(event, data) {
    if (event === 'stage') {
      let id = data.stage;
      if (id === 'gemini_pred' || id === 'nemotron') id = 'prediction';
      setStage(id, data.status, data.message);

      if (data.stage === 'hardware' && data.status === 'done' && data.data) {
        state.hw = data.data;
        toggleSources('hw', (state.hw.all_sources || []).length);
      }
      if (data.stage === 'software' && data.status === 'done' && data.data) {
        state.sw = data.data;
        toggleSources('sw', (state.sw.all_sources || []).length);
      }
      if (id === 'prediction' && data.status === 'done' && data.data) renderPrediction(data.data);
    }

    if (event === 'done') {
      state.sessionId = data.session_id || state.sessionId;
      if (data.error) {
        showError(typeof data.error === 'string' ? data.error : 'The estimate could not be completed.');
        return;
      }
      state.hw = data.hardware || {};
      state.sw = data.software || {};
      renderAll(data);
      els.empty.hidden = true;
      els.results.hidden = false;
      $('chat-suggest').hidden = false;
      appendChat('bot', 'Your estimate is ready. Ask about components, prices, sources, the team or the timeline.');
      if (window.innerWidth <= 960) {
        els.results.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      }
    }
  }

  /* ---------- Rendering ---------- */
  function renderPrediction(p) {
    const tc = p.total_cost_inr || {};
    $('cost-opt').textContent = fmt(tc.optimistic);
    $('cost-likely').textContent = fmt(tc.likely);
    $('cost-pess').textContent = fmt(tc.pessimistic);
    $('cost-summary').textContent = p.summary || '';

    // Where "likely" sits between the low and high case
    const lo = Number(tc.optimistic);
    const hi = Number(tc.pessimistic);
    const mid = Number(tc.likely);
    let pct = 50;
    if (hi > lo && mid >= lo) pct = Math.min(96, Math.max(4, ((mid - lo) / (hi - lo)) * 100));
    $('scale-lo').style.width = pct + '%';
    $('scale-mark').style.left = pct + '%';

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

    const eff = p.effort_months || {};
    $('bk-months').textContent = eff.likely ? `${eff.low} to ${eff.high} months, likely about ${eff.likely}` : '-';
    const conf = String(p.confidence || '');
    $('bk-conf').textContent = conf ? conf.charAt(0).toUpperCase() + conf.slice(1).toLowerCase() : '-';

    const flags = [...(p.duplicates_flagged || []), ...(p.missing_specs || [])];
    $('flags-section').hidden = flags.length === 0;
    $('flags-wrap').innerHTML = flags.length ? '<ul>' + flags.map((f) => `<li>${esc(f)}</li>`).join('') + '</ul>' : '';
  }

  function sourceBtn(type, idx, count) {
    return count > 0
      ? `<button type="button" class="src-btn" data-item-sources="${type}:${idx}">${count} ${plural(count, 'link', 'links')}</button>`
      : '<span class="block-note">None</span>';
  }

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
        const ps = it.price_summary || {};
        const models = (it.suggested_models || [])
          .map((m) => `<span class="tag tag-model">${esc(((m.maker || '') + ' ' + (m.model || '')).trim())}</span>`)
          .join('');
        const count = (it.sources || []).length || it.source_count || 0;
        return `<tr>
          <td><strong>${esc(it.name)}</strong>${it.spec ? `<small>${esc(it.spec)}</small>` : ''}</td>
          <td>${models || '-'}</td>
          <td>${ps.min ? fmtRange(ps.min, ps.max) : '<span class="block-note">Price not found</span>'}</td>
          <td>${sourceBtn('hardware', idx, count)}</td>
        </tr>`;
      })
      .join('');
    const t = hw.total || {};
    const foot = t.min || t.max
      ? `<tfoot><tr><td colspan="2">Total hardware</td><td colspan="2">${fmtRange(t.min, t.max)}</td></tr></tfoot>`
      : '';
    wrap.innerHTML = `<table>
      <thead><tr><th>Component</th><th>Suggested models</th><th>Live price range</th><th>Sources</th></tr></thead>
      <tbody>${rows}</tbody>${foot}
    </table>`;
  }

  function renderSoftware(sw) {
    const wrap = $('sw-table-wrap');
    const items = sw.items || [];
    toggleSources('sw', (sw.all_sources || []).length);

    if (!items.length) {
      wrap.innerHTML = '<p class="none">No software items required.</p>';
      return;
    }
    const maxHours = Math.max(1, ...items.map((it) => Number((it.effort || {}).hours_high) || 0));
    const rows = items
      .map((it, idx) => {
        const eff = it.effort || {};
        const ps = it.price_summary || {};
        const kind = String(it.kind || '');
        const kindCls = kind.includes('buy') ? 'tag-buy' : kind === 'process' ? 'tag-process' : 'tag-build';
        let detail = '-';
        if (eff.hours_likely) {
          const pct = Math.min(100, Math.round((eff.hours_likely / maxHours) * 100));
          detail = `${esc(eff.hours_low)} to ${esc(eff.hours_high)} hrs, likely about ${esc(eff.hours_likely)}
            <div class="meter"><span style="width:${pct}%"></span></div>
            ${eff.source ? `<small>${esc(eff.source)}</small>` : ''}`;
        } else if (ps.min || ps.max) {
          detail = `${fmtRange(ps.min, ps.max)}<small>Licence or SaaS</small>`;
        }
        const count = (it.sources || []).length || it.source_count || 0;
        return `<tr>
          <td><strong>${esc(it.name)}</strong></td>
          <td>${kind ? `<span class="tag ${kindCls}">${esc(kind)}</span>` : ''}${it.discipline ? `<span class="tag tag-plain">${esc(it.discipline)}</span>` : ''}</td>
          <td>${detail}</td>
          <td>${sourceBtn('software', idx, count)}</td>
        </tr>`;
      })
      .join('');
    const e = sw.effort || {};
    const foot = e.months_likely
      ? `<tfoot><tr><td colspan="2">Total development effort</td><td colspan="2">${esc(e.total_hours_low)} to ${esc(e.total_hours_high)} hrs, about ${esc(e.months_likely)} months likely</td></tr></tfoot>`
      : '';
    wrap.innerHTML = `<table>
      <thead><tr><th>Deliverable</th><th>Type</th><th>Effort or cost</th><th>Sources</th></tr></thead>
      <tbody>${rows}</tbody>${foot}
    </table>`;
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
    if (data.prediction && !data.prediction.error) {
      renderPrediction(data.prediction);
    } else if (data.prediction && data.prediction.error) {
      $('cost-summary').textContent = 'The total forecast failed: ' + data.prediction.error;
    }
  }

  /* ---------- Sources dialog ---------- */
  function openSources(title, list) {
    $('modal-title').textContent = `${title} (${list.length})`;
    const body = $('modal-content');
    if (!list.length) {
      body.innerHTML = '<p class="none" style="padding:24px 0">No external links found for this item.</p>';
    } else {
      body.innerHTML = list
        .map((s) => {
          const url = safeUrl(s.url);
          let host = '';
          try { host = new URL(url).hostname.replace(/^www\./, ''); } catch (e) { /* no host */ }
          const label = esc(s.title || s.url || 'Untitled source');
          return `<div class="source">
            <div class="source-meta">
              ${s.item ? `<span class="source-chip item">${esc(s.item)}</span>` : ''}
              ${host ? `<span class="source-chip">${esc(host)}</span>` : ''}
            </div>
            ${url ? `<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>` : `<span class="source-link">${label}</span>`}
            ${s.snippet ? `<p class="source-snippet">${esc(s.snippet)}</p>` : ''}
            ${url ? `<p class="source-url">${esc(url)}</p>` : ''}
          </div>`;
        })
        .join('');
    }
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

  /* ---------- Chat ---------- */
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
    $('ask-btn').focus();
  }

  function appendChat(cls, text) {
    const el = document.createElement('div');
    el.className = 'msg ' + cls;
    el.textContent = text;
    els.chatLog.appendChild(el);
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
    return el;
  }

  async function sendChat(text) {
    const msg = String(text ?? els.chatInput.value).trim();
    if (!msg) return;
    els.chatInput.value = '';
    appendChat('user', msg);
    const pending = appendChat('bot thinking', 'Thinking...');
    try {
      const res = await fetch('/api/chat', {
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
    }
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }

  /* ---------- Wiring ---------- */
  const modeButtons = Array.from(document.querySelectorAll('.mode'));
  modeButtons.forEach((b, i) => {
    b.addEventListener('click', () => setMode(b.dataset.mode));
    b.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const next = modeButtons[(i + (e.key === 'ArrowRight' ? 1 : modeButtons.length - 1)) % modeButtons.length];
      next.focus();
      setMode(next.dataset.mode);
    });
  });

  els.text.addEventListener('input', refreshInput);
  els.text.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !els.run.disabled) startPipeline();
  });
  els.form.addEventListener('submit', (e) => {
    e.preventDefault();
    startPipeline();
  });

  bindDropzone('image');
  bindDropzone('pdf');

  document.addEventListener('click', (e) => {
    const clear = e.target.closest('[data-clear]');
    if (clear) {
      e.preventDefault();
      e.stopPropagation();
      clearFile(clear.dataset.clear);
      return;
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
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) els.dialog.close();
    }
  });

  $('ask-btn').addEventListener('click', openChat);
  $('chat-close').addEventListener('click', closeChat);
  els.scrim.addEventListener('click', closeChat);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && els.chat.classList.contains('is-open')) closeChat();
  });
  $('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    sendChat();
  });

  setMode('text');
})();