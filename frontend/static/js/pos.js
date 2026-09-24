/*
 * pos.js — shared helpers for every POS screen.
 *
 *   POS.api(path, {method, body})   fetch + auth + JSON; throws POS.ApiError
 *   POS.esc(text)                   escape before putting data into innerHTML
 *   POS.money(n) / POS.num(n)       "NPR 1,243.00" / "1,243.00" (Nepali grouping)
 *   POS.time(iso) / POS.dateTime()  shown in Nepal time whatever the device clock
 *   POS.toast / POS.confirm / POS.prompt   touch-friendly feedback and dialogs
 *   POS.print(url) / POS.printReceipt(billId)   print through a hidden frame
 *   POS.nav(active)                 top navigation, filtered by role
 */
(function () {
  'use strict';

  const TZ = 'Asia/Kathmandu';
  const moneyFmt = new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const timeFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
  const dateFmt = new Intl.DateTimeFormat('en-US', { timeZone: TZ, month: 'short', day: 'numeric' });
  const isoDateFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TZ });   // → YYYY-MM-DD

  // ── Session ────────────────────────────────────────────────────────────────
  function token() { return localStorage.getItem('token'); }
  function user() {
    try { return JSON.parse(localStorage.getItem('user') || 'null') || {}; } catch { return {}; }
  }
  function setSession(data) {
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    if (data.user && data.user.restaurant_slug) localStorage.setItem('restaurant_code', data.user.restaurant_slug);
  }
  function clearSession() {
    // Keep restaurant_code so the next person only needs their PIN
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
  function goLogin(mode) {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = `/login?next=${next}${mode ? '&mode=' + mode : ''}`;
  }
  function requireLogin() {
    if (!token()) { goLogin(); return false; }
    return true;
  }
  /** Redirect away unless the signed-in role is allowed on this page. */
  function guard(roles) {
    if (!requireLogin()) return false;
    const u = user();
    if (roles && !roles.includes(u.role)) {
      location.href = u.home || '/login';
      return false;
    }
    return true;
  }

  // ── API ────────────────────────────────────────────────────────────────────
  class ApiError extends Error {
    constructor(status, message, data, headers) {
      super(message);
      this.status = status;
      this.data = data;
      this.headers = headers;
    }
  }

  async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    const t = token();
    if (t) headers['Authorization'] = `Bearer ${t}`;
    const init = { method: opts.method || 'GET', headers, credentials: 'same-origin' };
    if (opts.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body);
    }
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      throw new ApiError(0, 'Cannot reach the POS server — check the Wi-Fi / network connection.');
    }
    if (res.status === 401 && !opts.noRedirect) {
      clearSession();
      goLogin();
      throw new ApiError(401, 'Session expired — please log in again.');
    }
    if (res.status === 204) return null;
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      let msg = `Something went wrong (${res.status})`;
      if (data && data.detail) {
        msg = typeof data.detail === 'string'
          ? data.detail
          : data.detail.map(d => `${(d.loc || []).slice(-1)[0] || ''} ${d.msg}`.trim()).join('; ');
      }
      throw new ApiError(res.status, msg, data, res.headers);
    }
    return data;
  }

  // ── Formatting ─────────────────────────────────────────────────────────────
  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function num(n) { return moneyFmt.format(Number(n) || 0); }
  function money(n) { return 'NPR ' + num(n); }
  function toDate(iso) { return iso ? new Date(iso) : null; }
  function time(iso) { const d = toDate(iso); return d ? timeFmt.format(d) : ''; }
  function date(iso) { const d = toDate(iso); return d ? dateFmt.format(d) : ''; }
  function dateTime(iso) { const d = toDate(iso); return d ? `${dateFmt.format(d)}, ${timeFmt.format(d)}` : ''; }
  function todayISO(offsetDays = 0) {
    return isoDateFmt.format(new Date(Date.now() + offsetDays * 86400000));
  }
  function duration(minutes) {
    minutes = Math.max(0, Math.floor(minutes || 0));
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 24 * 60) return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`;
    return `${Math.floor(minutes / 1440)}d ${Math.floor((minutes % 1440) / 60)}h`;
  }
  function label(key) {
    return ({ dine_in: 'Dine in', takeaway: 'Takeaway', delivery: 'Delivery' })[key]
      || String(key || '').replace(/_/g, ' ');
  }
  function debounce(fn, ms = 250) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  // ── Toasts ─────────────────────────────────────────────────────────────────
  function toastHost() {
    let host = document.getElementById('pos-toasts');
    if (!host) {
      host = document.createElement('div');
      host.id = 'pos-toasts';
      host.className = 'fixed bottom-4 left-1/2 -translate-x-1/2 z-[200] flex flex-col items-center gap-2 w-[min(92vw,28rem)] pointer-events-none';
      document.body.appendChild(host);
    }
    return host;
  }
  /** POS.toast('Saved') · POS.toast('Failed', {type:'error'}) · {action:{label, fn}} */
  function toast(message, opts = {}) {
    const type = opts.type || 'ok';
    const colors = { ok: 'bg-gray-900', error: 'bg-red-600', info: 'bg-blue-700', warn: 'bg-amber-600' };
    const el = document.createElement('div');
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.className = `${colors[type] || colors.ok} text-white text-sm font-medium rounded-xl shadow-lg px-4 py-3 flex items-center gap-3 w-full pointer-events-auto`;
    el.innerHTML = `<span class="flex-1">${esc(message)}</span>`;
    if (opts.action) {
      const btn = document.createElement('button');
      btn.className = 'shrink-0 font-bold underline underline-offset-2 px-1';
      btn.textContent = opts.action.label;
      btn.onclick = () => { el.remove(); opts.action.fn(); };
      el.appendChild(btn);
    }
    toastHost().appendChild(el);
    setTimeout(() => el.remove(), opts.timeout || (opts.action ? 7000 : type === 'error' ? 5000 : 3000));
    return el;
  }
  function fail(err) { toast(err && err.message ? err.message : String(err), { type: 'error' }); }

  // ── Dialogs (Promise-based, big touch targets) ─────────────────────────────
  function modal(html, { onMount, wide } = {}) {
    return new Promise(resolve => {
      const wrap = document.createElement('div');
      wrap.className = 'fixed inset-0 z-[150] bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4';
      wrap.innerHTML = `<div class="bg-white w-full ${wide ? 'sm:max-w-lg' : 'sm:max-w-sm'} max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl shadow-2xl p-5">${html}</div>`;
      const close = value => { wrap.remove(); document.removeEventListener('keydown', onKey); resolve(value); };
      const onKey = e => { if (e.key === 'Escape') close(null); };
      wrap.addEventListener('click', e => { if (e.target === wrap) close(null); });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(wrap);
      onMount && onMount(wrap, close);
    });
  }

  function confirm(message, opts = {}) {
    const okClass = opts.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700';
    return modal(`
      <h2 class="text-lg font-bold text-gray-900 mb-1">${esc(opts.title || 'Are you sure?')}</h2>
      <p class="text-sm text-gray-600 mb-5">${esc(message)}</p>
      <div class="flex gap-2">
        <button data-x="no" class="flex-1 py-3 rounded-xl border text-gray-700 font-medium hover:bg-gray-50">${esc(opts.cancelText || 'Cancel')}</button>
        <button data-x="yes" class="flex-1 py-3 rounded-xl text-white font-semibold ${okClass}">${esc(opts.okText || 'Yes')}</button>
      </div>`, {
      onMount: (w, close) => {
        w.querySelector('[data-x=no]').onclick = () => close(false);
        const yes = w.querySelector('[data-x=yes]');
        yes.onclick = () => close(true);
        yes.focus();
      },
    }).then(v => v === true);
  }

  /** Resolves to the entered text, or null if cancelled.  opts.chips = quick answers. */
  function prompt(title, opts = {}) {
    const chips = (opts.chips || []).map(c =>
      `<button type="button" data-chip="${esc(c)}" class="px-3 py-2 rounded-full bg-gray-100 hover:bg-gray-200 text-sm">${esc(c)}</button>`).join('');
    return modal(`
      <form>
        <h2 class="text-lg font-bold text-gray-900 mb-1">${esc(title)}</h2>
        ${opts.message ? `<p class="text-sm text-gray-600 mb-3">${esc(opts.message)}</p>` : ''}
        ${chips ? `<div class="flex flex-wrap gap-2 mb-3">${chips}</div>` : ''}
        <input name="v" type="${opts.type || 'text'}" ${opts.inputmode ? `inputmode="${opts.inputmode}"` : ''}
          class="w-full border rounded-xl px-3 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="${esc(opts.placeholder || '')}" value="${esc(opts.value || '')}" autocomplete="off" />
        <p data-err class="hidden text-sm text-red-600 mt-2"></p>
        <div class="flex gap-2 mt-4">
          <button type="button" data-x="no" class="flex-1 py-3 rounded-xl border text-gray-700 font-medium hover:bg-gray-50">Cancel</button>
          <button type="submit" class="flex-1 py-3 rounded-xl text-white font-semibold ${opts.danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}">${esc(opts.okText || 'OK')}</button>
        </div>
      </form>`, {
      onMount: (w, close) => {
        const input = w.querySelector('input');
        const err = w.querySelector('[data-err]');
        w.querySelector('[data-x=no]').onclick = () => close(null);
        w.querySelectorAll('[data-chip]').forEach(b => b.onclick = () => {
          if (opts.appendChips && input.value.trim()) input.value = `${input.value.trim()}, ${b.dataset.chip}`;
          else input.value = b.dataset.chip;
          input.focus();
        });
        w.querySelector('form').onsubmit = e => {
          e.preventDefault();
          const v = input.value.trim();
          if (opts.required && !v) { err.textContent = opts.requiredText || 'Required'; err.classList.remove('hidden'); return; }
          close(v);
        };
        setTimeout(() => { input.focus(); input.select(); }, 30);
      },
    });
  }

  // ── Printing ───────────────────────────────────────────────────────────────
  function print(url) {
    const frame = document.createElement('iframe');
    frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden';
    frame.src = url + (url.includes('?') ? '&' : '?') + 'autoprint=1';
    document.body.appendChild(frame);
    setTimeout(() => frame.remove(), 120000);
  }
  async function printReceipt(billId) {
    try { await api(`/api/billing/bills/${billId}/print`, { method: 'PATCH' }); } catch (e) { /* still print */ }
    print(`/receipt/${billId}`);
  }
  function printKot(orderId, kotNumber) { print(`/kot-print/${orderId}/${kotNumber}`); }

  // ── Sound (browsers only allow audio after the first tap) ──────────────────
  let audioCtx = null;
  function unlockAudio() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
    } catch { /* no audio support */ }
    return audioReady();
  }
  function audioReady() { return !!audioCtx && audioCtx.state === 'running'; }
  function beep(times = 2, freq = 880) {
    if (!audioReady()) return false;
    for (let i = 0; i < times; i++) {
      const start = audioCtx.currentTime + i * 0.28;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.35, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.22);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(start);
      osc.stop(start + 0.24);
    }
    return true;
  }
  document.addEventListener('pointerdown', unlockAudio, { once: true });

  // ── Navigation ─────────────────────────────────────────────────────────────
  const STAFF = ['admin', 'cashier', 'waiter', 'superadmin'];
  const LINKS = [
    { href: '/dashboard',    label: 'Dashboard', icon: '📊', roles: ['admin', 'superadmin'] },
    { href: '/tables',       label: 'Floor',     icon: '🪑', roles: STAFF },
    { href: '/orders',       label: 'Quick Order', icon: '➕', roles: STAFF },
    { href: '/kitchen',      label: 'Kitchen',   icon: '👨‍🍳', roles: [...STAFF, 'kitchen'] },
    { href: '/reservations', label: 'Bookings',  icon: '📅', roles: STAFF },
    { href: '/billing',      label: 'Billing',   icon: '🧾', roles: ['admin', 'cashier', 'superadmin'] },
    { href: '/menu',         label: 'Menu',      icon: '📖', roles: ['admin', 'superadmin'], more: true },
    { href: '/inventory',    label: 'Inventory', icon: '📦', roles: ['admin', 'superadmin'], more: true },
    { href: '/reports',      label: 'Reports',   icon: '📈', roles: ['admin', 'cashier', 'superadmin'], more: true },
    { href: '/users',        label: 'Staff',     icon: '👥', roles: ['admin', 'superadmin'], more: true },
    { href: '/settings',     label: 'Settings',  icon: '⚙️', roles: ['admin', 'superadmin'], more: true },
  ];

  let readyCount = null;

  function nav(active, opts = {}) {
    const host = document.getElementById('pos-nav');
    if (!host) return;
    const u = user();
    const links = LINKS.filter(l => l.roles.includes(u.role));
    const cls = l => l.href === active
      ? 'bg-gray-700 text-white'
      : 'text-gray-300 hover:bg-gray-800 hover:text-white';
    const linkHtml = l => `<a href="${l.href}" class="px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap ${cls(l)}">${l.icon} ${esc(l.label)}</a>`;
    const primary = links.filter(l => !l.more);
    const more = links.filter(l => l.more);
    const moreActive = more.some(l => l.href === active);
    const initials = (u.full_name || u.username || '?').trim().charAt(0).toUpperCase();

    host.innerHTML = `
      <header class="bg-gray-900 text-white shadow-md sticky top-0 z-40 print:hidden">
        <div class="px-3 sm:px-4 h-14 flex items-center gap-1.5">
          <a href="${esc(u.home || '/tables')}" class="flex items-center gap-2 mr-2 shrink-0" title="Home">
            <span class="text-xl">🍽️</span>
            <span class="font-bold hidden sm:block truncate max-w-[11rem]">${esc(u.restaurant_name || 'Restaurant POS')}</span>
          </a>
          <nav class="hidden lg:flex items-center gap-1">
            ${primary.map(linkHtml).join('')}
            ${more.length ? `
            <div class="relative">
              <button data-dd="more" class="px-3 py-2 rounded-lg text-sm font-medium ${moreActive ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-800'}">More ▾</button>
              <div data-menu="more" class="hidden absolute left-0 mt-1 w-48 bg-white text-gray-800 rounded-xl shadow-xl py-1 z-50">
                ${more.map(l => `<a href="${l.href}" class="block px-4 py-2 text-sm hover:bg-gray-100 ${l.href === active ? 'font-semibold text-blue-700' : ''}">${l.icon} ${esc(l.label)}</a>`).join('')}
              </div>
            </div>` : ''}
          </nav>
          <div class="flex-1"></div>
          ${opts.extra || ''}
          <div class="relative">
            <button id="nav-ready" data-dd="ready" class="hidden items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold px-3 py-1.5 rounded-full">
              🔔 <span id="nav-ready-count">0</span><span class="hidden sm:inline">ready</span>
            </button>
            <div data-menu="ready" class="hidden absolute right-0 mt-2 w-80 max-h-[70vh] overflow-y-auto bg-white text-gray-800 rounded-xl shadow-xl z-50" id="nav-ready-list"></div>
          </div>
          <span id="nav-clock" class="hidden md:block font-mono text-sm text-gray-400 px-2"></span>
          <div class="relative">
            <button data-dd="user" class="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full hover:bg-gray-800">
              <span class="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-sm font-bold">${esc(initials)}</span>
              <span class="hidden md:block text-left leading-tight">
                <span class="block text-sm">${esc(u.full_name || u.username || '')}</span>
                <span class="block text-xs text-gray-400 capitalize">${esc(u.role || '')}</span>
              </span>
            </button>
            <div data-menu="user" class="hidden absolute right-0 mt-2 w-52 bg-white text-gray-800 rounded-xl shadow-xl py-1 z-50">
              <button data-act="switch" class="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-100">🔢 Switch user (PIN)</button>
              <button data-act="logout" class="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50">⎋ Log out</button>
            </div>
          </div>
          <button data-dd="mobile" class="lg:hidden ml-1 w-10 h-10 rounded-lg hover:bg-gray-800 text-xl" aria-label="Menu">☰</button>
        </div>
        <div data-menu="mobile" class="hidden lg:hidden border-t border-gray-800 px-3 py-2 grid grid-cols-2 sm:grid-cols-3 gap-1">
          ${links.map(linkHtml).join('')}
        </div>
      </header>`;

    // Dropdowns: one open at a time, close on outside tap
    host.querySelectorAll('[data-dd]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const menu = host.querySelector(`[data-menu="${btn.dataset.dd}"]`);
        const open = menu.classList.contains('hidden');
        host.querySelectorAll('[data-menu]').forEach(m => m.classList.add('hidden'));
        if (open) menu.classList.remove('hidden');
      });
    });
    host.querySelectorAll('[data-menu]').forEach(m => m.addEventListener('click', e => e.stopPropagation()));
    document.addEventListener('click', () => host.querySelectorAll('[data-menu]').forEach(m => m.classList.add('hidden')));

    host.querySelector('[data-act=logout]').onclick = logout;
    host.querySelector('[data-act=switch]').onclick = () => { clearSession(); goLogin('pin'); };

    const clock = document.getElementById('nav-clock');
    const tick = () => { clock.textContent = timeFmt.format(new Date()); };
    tick();
    setInterval(tick, 15000);

    if (u.role && u.role !== 'kitchen' && u.role !== 'superadmin' && opts.readyAlerts !== false) {
      pollReady();
      setInterval(pollReady, 15000);
    }
  }

  async function pollReady() {
    let data;
    try { data = await api('/api/kitchen/ready', { noRedirect: true }); } catch { return; }
    const btn = document.getElementById('nav-ready');
    if (!btn) return;
    const n = data.ready_items;
    btn.classList.toggle('hidden', n === 0);
    btn.classList.toggle('flex', n > 0);
    document.getElementById('nav-ready-count').textContent = n;
    if (readyCount !== null && n > readyCount) {
      beep(2, 988);
      const first = data.orders[0];
      if (first) toast(`🔔 Ready: ${first.table_number ? 'Table ' + first.table_number : label(first.order_type) + (first.customer_name ? ' · ' + first.customer_name : '')}`, { type: 'info' });
    }
    readyCount = n;
    document.getElementById('nav-ready-list').innerHTML = data.orders.length === 0
      ? '<p class="p-4 text-sm text-gray-500">Nothing waiting.</p>'
      : data.orders.map(o => `
        <div class="p-3 border-b last:border-0">
          <div class="flex items-center justify-between gap-2 mb-1">
            <span class="font-semibold">${o.table_number ? 'Table ' + esc(o.table_number) : esc(label(o.order_type))}${o.customer_name ? ` · ${esc(o.customer_name)}` : ''}</span>
            <button data-serve="${o.order_id}" class="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg font-semibold">Served ✓</button>
          </div>
          <p class="text-sm text-gray-600">${o.items.map(i => `${i.quantity}× ${esc(i.name)}`).join(', ')}</p>
        </div>`).join('');
    document.querySelectorAll('#nav-ready-list [data-serve]').forEach(b => b.onclick = async () => {
      try {
        await api(`/api/orders/${b.dataset.serve}/serve-ready`, { method: 'POST' });
        toast('Marked as served');
        document.dispatchEvent(new CustomEvent('pos:served'));
        pollReady();
      } catch (e) { fail(e); }
    });
  }

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST', noRedirect: true }); } catch { /* ignore */ }
    clearSession();
    location.href = '/login';
  }

  window.POS = {
    token, user, setSession, clearSession, requireLogin, guard, goLogin, logout,
    api, ApiError, esc, num, money, time, date, dateTime, todayISO, duration, label, debounce,
    toast, fail, confirm, prompt, modal, print, printReceipt, printKot,
    unlockAudio, audioReady, beep, nav, refreshReady: pollReady,
  };
})();
