/* GitHub Activity Generator — UI logic · author: kotmir */
(() => {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
  };

  const PRESETS = {
    light:  { frequency: 40, max_commits: 4,  no_weekends: true },
    normal: { frequency: 80, max_commits: 10, no_weekends: false },
    heavy:  { frequency: 95, max_commits: 20, no_weekends: false },
  };
  const FIELDS = ['repository', 'user_name', 'user_email', 'days_before',
    'days_after', 'frequency', 'max_commits', 'mode', 'seed', 'output_dir'];

  let lang = store.get('gag.lang') ||
    ((navigator.language || 'ru').toLowerCase().startsWith('ru') ? 'ru' : 'en');
  let state = 'idle';
  let since = 0;
  let pollTimer = null;
  let previewTimer = null;
  let previewData = null;
  let info = null;
  let online = false;
  const logLines = [];   // [{ts, level, text}] — for copy / re-render

  /* ---------------- i18n ---------------- */
  function t(key, params) {
    let s = (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
    Object.keys(params || {}).forEach((k) => { s = s.split('{' + k + '}').join(params[k]); });
    return s;
  }

  function applyI18n() {
    document.documentElement.lang = lang;
    $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$('[data-i18n-html]').forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
    $$('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$('[data-i18n-title]').forEach((el) => { el.title = t(el.dataset.i18nTitle); });
    $$('.seg button').forEach((b) => b.classList.toggle('active', b.dataset.lang === lang));
    renderGit();
    renderState();
    renderStats();
    renderHeat();
    renderLog();
    applyIdentityPlaceholders();
  }

  /* ---------------- API ---------------- */
  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ lang }, body)),
    };
    const sep = path.includes('?') ? '&' : '?';
    const url = body === undefined ? path + sep + 'lang=' + lang : path;
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      setOnline(false);
      throw e;
    }
    setOnline(true);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.error || res.statusText);
      err.field = data.field;
      throw err;
    }
    return data;
  }

  function setOnline(value) {
    if (online === value && info !== null) return;
    online = value;
    $('#offlineBanner').hidden = value;
    $('#stopServer').hidden = !value;
    $('#btnGenerate').disabled = !value || state === 'running';
  }

  /* ---------------- form ---------------- */
  function readConfig() {
    const v = (id) => $('#' + id).value.trim();
    return {
      repository: v('repository') || null,
      user_name: v('user_name') || null,
      user_email: v('user_email') || null,
      days_before: v('days_before'),
      days_after: v('days_after'),
      frequency: v('frequency'),
      max_commits: v('max_commits'),
      no_weekends: $('#no_weekends').checked,
      mode: $('#mode').value,
      seed: v('seed'),
      output_dir: v('output_dir') || 'output',
    };
  }

  function saveForm() {
    const data = readConfig();
    data.repository = null;            // never persist the URL (may hold tokens)
    store.set('gag.form', JSON.stringify(data));
  }

  function loadForm() {
    let data = {};
    try { data = JSON.parse(store.get('gag.form') || '{}'); } catch (e) { data = {}; }
    FIELDS.forEach((id) => {
      if (data[id] !== undefined && data[id] !== null && id !== 'repository') {
        $('#' + id).value = data[id];
      }
    });
    if (typeof data.no_weekends === 'boolean') $('#no_weekends').checked = data.no_weekends;
    if (!$('#seed').value) $('#seed').value = randomSeed();
    syncOutputs();
  }

  function randomSeed() { return String(Math.floor(Math.random() * 1e9)); }

  function syncOutputs() {
    $('#freqOut').textContent = $('#frequency').value + '%';
    $('#maxOut').textContent = $('#max_commits').value;
  }

  function clearInvalid() { $$('input.invalid').forEach((el) => el.classList.remove('invalid')); }

  function showNotice(text, isError) {
    const el = $('#notice');
    el.textContent = text || '';
    el.hidden = !text;
    el.classList.toggle('err', !!isError);
  }

  function applyIdentityPlaceholders() {
    const id = (info && info.identity) || {};
    $('#user_name').placeholder = id.name || t('ph.global');
    $('#user_email').placeholder = id.email || t('ph.global');
  }

  /* ---------------- preview / heatmap ---------------- */
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(loadPreview, 250);
  }

  async function loadPreview() {
    clearInvalid();
    const cfg = readConfig();
    cfg.repository = null;             // not needed for the preview
    try {
      previewData = await api('/api/preview', cfg);
      showNotice('');
      if (previewData.total > 3000) showNotice(t('warn.many'), false);
      else if (+cfg.days_after > 0) showNotice(t('warn.future'), false);
    } catch (e) {
      if (!online) return;
      showNotice(e.message, true);
      if (e.field && $('#' + e.field)) $('#' + e.field).classList.add('invalid');
      return;
    }
    renderStats();
    renderHeat();
  }

  function renderStats() {
    const d = previewData;
    $('#stCommits').textContent = d ? d.total : '–';
    $('#stDays').textContent = d ? d.active_days : '–';
    $('#stMax').textContent = d ? d.max_per_day : '–';
    $('#stAvg').textContent = d && d.active_days ? (d.total / d.active_days).toFixed(1) : '–';
  }

  function renderHeat() {
    const box = $('#heat');
    box.innerHTML = '';
    const d = previewData;
    if (!d || !d.start) return;
    const [y, m, day] = d.start.split('-').map(Number);
    const start = new Date(y, m - 1, day);
    const lead = start.getDay();                     // Sunday first, like GitHub
    const max = Math.max(1, d.max_per_day);
    const frag = document.createDocumentFragment();
    d.counts.forEach((n, i) => {
      const date = new Date(y, m - 1, day + i);
      const idx = i + lead;
      const week = Math.floor(idx / 7);
      const dow = idx % 7;
      if (date.getDate() === 1 || (i === 0 && date.getDate() <= 20)) {
        const label = document.createElement('span');
        label.className = 'month';
        label.style.gridColumn = String(week + 1);
        label.textContent = date.toLocaleDateString(lang, { month: 'short' });
        frag.appendChild(label);
      }
      const cell = document.createElement('div');
      const level = n === 0 ? 0 : Math.min(4, Math.ceil((n / max) * 4));
      cell.className = 'cell' + (level ? ' l' + level : '');
      cell.style.gridColumn = String(week + 1);
      cell.style.gridRow = String(dow + 2);
      const label = date.toLocaleDateString(lang, { year: 'numeric', month: 'short', day: 'numeric' });
      cell.title = t('cell.title', { date: label, n });
      frag.appendChild(cell);
    });
    box.appendChild(frag);
    const scroller = box.parentElement;
    scroller.scrollLeft = scroller.scrollWidth;
  }

  /* ---------------- run / poll ---------------- */
  function renderGit() {
    const badge = $('#gitBadge');
    if (!online || !info) { badge.hidden = true; return; }
    badge.hidden = false;
    badge.classList.toggle('bad', !info.git);
    badge.textContent = info.git ? t('git.ok', { v: info.git }) : t('git.missing');
  }

  function renderState() {
    const pill = $('#statePill');
    pill.className = 'state-pill ' + state;
    pill.textContent = t('state.' + state);
    const running = state === 'running';
    $('#btnGenerate').disabled = running || !online;
    $('#btnCancel').hidden = !running;
    $('#progress').classList.toggle('active', running);
  }

  function setProgress(done, total) {
    const pct = total ? Math.floor((done * 100) / total) : 0;
    $('#progressBar').style.width = pct + '%';
    $('#progressText').textContent = total ? done + ' / ' + total : '';
    $('#progressPct').textContent = total ? pct + '%' : '';
  }

  const pad = (n) => String(n).padStart(2, '0');
  function stamp(ts) {
    const d = new Date(ts * 1000);
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  function appendLog(ev) {
    logLines.push(ev);
    const box = $('#console');
    const empty = box.querySelector('.empty');
    if (empty) empty.remove();
    const stick = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
    box.appendChild(lineEl(ev));
    if (stick) box.scrollTop = box.scrollHeight;
  }

  function lineEl(ev) {
    const row = document.createElement('div');
    row.className = 'ln ' + ev.level;
    const ts = document.createElement('span');
    ts.className = 'ts';
    ts.textContent = stamp(ev.ts);
    row.appendChild(ts);
    row.appendChild(document.createTextNode(ev.text));
    return row;
  }

  function renderLog() {
    const box = $('#console');
    box.innerHTML = '';
    if (!logLines.length) {
      const e = document.createElement('div');
      e.className = 'empty';
      e.textContent = t('log.empty');
      box.appendChild(e);
      return;
    }
    logLines.forEach((ev) => box.appendChild(lineEl(ev)));
    box.scrollTop = box.scrollHeight;
  }

  function applyStatus(s) {
    s.events.forEach(appendLog);
    since = s.next;
    state = s.state;
    setProgress(s.progress.done, s.progress.total);
    renderState();
    const result = $('#result');
    if (s.state === 'done' && s.result) {
      $('#resultPath').textContent = s.result.path;
      result.hidden = false;
    } else {
      result.hidden = true;
    }
    if (state === 'running') {
      clearTimeout(pollTimer);
      pollTimer = setTimeout(poll, 450);
    }
  }

  async function poll() {
    try {
      applyStatus(await api('/api/status?since=' + since));
    } catch (e) {
      clearTimeout(pollTimer);
      if (state === 'running') pollTimer = setTimeout(poll, 1500);
    }
  }

  async function resync() {           // re-read the whole log (language switch / reload)
    logLines.length = 0;
    since = 0;
    renderLog();
    try { applyStatus(await api('/api/status?since=0')); } catch (e) { /* offline */ }
  }

  async function start() {
    clearInvalid();
    const cfg = readConfig();
    if (cfg.repository &&
        !window.confirm(t('confirm.push', { repo: cfg.repository.replace(/\/\/[^/@\s]+@/, '//***@') }))) {
      return;
    }
    try {
      await api('/api/start', cfg);
    } catch (e) {
      showNotice(e.message, true);
      if (e.field && $('#' + e.field)) $('#' + e.field).classList.add('invalid');
      return;
    }
    showNotice('');
    logLines.length = 0;
    since = 0;
    renderLog();
    setProgress(0, 0);
    state = 'running';
    renderState();
    poll();
  }

  /* ---------------- init ---------------- */
  async function init() {
    document.documentElement.dataset.theme = store.get('gag.theme') || 'dark';

    loadForm();
    applyI18n();

    if (location.protocol === 'file:') {         // opened without the server
      setOnline(false);
      return;
    }
    try {
      info = await api('/api/info');
    } catch (e) {
      setOnline(false);
      return;
    }
    renderGit();
    applyIdentityPlaceholders();
    await loadPreview();
    resync();
  }

  /* ---------------- events ---------------- */
  $('#settingsForm').addEventListener('input', (e) => {
    syncOutputs();
    saveForm();
    schedulePreview();
    e.target.classList && e.target.classList.remove('invalid');
  });
  $('#settingsForm').addEventListener('submit', (e) => { e.preventDefault(); start(); });
  $('#btnCancel').addEventListener('click', () => api('/api/cancel', {}).catch(() => {}));
  $('#btnDice').addEventListener('click', () => {
    $('#seed').value = randomSeed();
    saveForm();
    loadPreview();
  });
  $$('.chip').forEach((chip) => chip.addEventListener('click', () => {
    const p = PRESETS[chip.dataset.preset];
    $('#frequency').value = p.frequency;
    $('#max_commits').value = p.max_commits;
    $('#no_weekends').checked = p.no_weekends;
    syncOutputs();
    saveForm();
    loadPreview();
  }));
  $$('.seg button').forEach((b) => b.addEventListener('click', () => {
    lang = b.dataset.lang;
    store.set('gag.lang', lang);
    applyI18n();
    if (online) { loadPreview(); resync(); }
  }));
  $('#themeBtn').addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    store.set('gag.theme', next);
  });
  $('#btnCopy').addEventListener('click', async () => {
    const text = logLines.map((l) => '[' + stamp(l.ts) + '] ' + l.text).join('\n');
    try { await navigator.clipboard.writeText(text); } catch (e) { return; }
    const btn = $('#btnCopy');
    const old = btn.textContent;
    btn.textContent = t('log.copied');
    setTimeout(() => { btn.textContent = old; }, 1200);
  });
  $('#btnClear').addEventListener('click', () => { logLines.length = 0; renderLog(); });
  $('#btnLogFile').addEventListener('click', () => { window.location.href = '/api/log/download'; });
  $('#btnOpen').addEventListener('click', () => api('/api/open', {}).catch((e) => showNotice(e.message, true)));
  $('#stopServer').addEventListener('click', async () => {
    try { await api('/api/shutdown', {}); } catch (e) { /* ignore */ }
    online = false;
    document.body.innerHTML = '<p style="padding:40px;font:16px system-ui;color:#a3e635;background:#0a0f06;'
      + 'min-height:100vh;margin:0">' + t('server.stopped') + '</p>';
  });

  init();
})();
