/*
 * payment.js — the Bill & payment dialog, shared by the order screen and the Billing page.
 *
 *   PaymentDialog.open(orderId, { onPaid(bill), onClose() })
 *
 * The customer pays last: the cashier checks the bill on screen (discount, service
 * charge, PAN), takes payment, and then prints the final bill.  Confirming calls
 * /api/billing/checkout, which issues the bill number, records the payment(s), closes
 * the order and frees the table.  Totals always come from the server
 * (/api/billing/preview) so VAT and service charge are computed in exactly one place.
 */
(function () {
  'use strict';
  const { api, esc, money, num, toast, fail } = POS;

  const ICONS = { cash: '💵', card: '💳', qr: '📱', esewa: '🟢', khalti: '🟣', bank: '🏦' };
  const AUTO_PRINT_KEY = 'pos.autoPrintReceipt';
  let methodsCache = null;

  async function loadMethods() {
    if (!methodsCache) methodsCache = await api('/api/billing/payment-methods');
    return methodsCache;
  }

  /** Amounts a guest is likely to hand over: exact, then round-ups to Nepali notes. */
  function quickCash(total) {
    const up = step => Math.ceil(total / step) * step;
    const values = new Set([up(1), up(50), up(100), up(500), up(1000), up(1000) + 1000]);
    return [...values].filter(v => v >= total).sort((a, b) => a - b).slice(0, 5);
  }

  function round2(n) { return Math.round((Number(n) || 0) * 100) / 100; }

  class PaymentDialog {
    constructor(orderId, opts = {}) {
      this.orderId = orderId;
      this.opts = opts;
      this.st = {
        discountType: null, discountValue: 0, includeService: true,
        customerName: '', customerPan: '', showCustomer: false,
        method: null, tendered: '', reference: '',
        split: false, rows: [],
        busy: false, bill: null, dyn: null,
        issued: null,      // bill created (and printed) but not yet paid
      };
    }

    static open(orderId, opts) {
      const d = new PaymentDialog(orderId, opts);
      d.mount();
      return d;
    }

    // ── Lifecycle ───────────────────────────────────────────────────────────
    async mount() {
      this.root = document.createElement('div');
      this.root.className = 'fixed inset-0 z-[120] bg-black/60 flex items-stretch sm:items-center justify-center sm:p-4';
      this.root.innerHTML = `<div class="bg-white w-full sm:max-w-3xl sm:rounded-2xl shadow-2xl flex flex-col max-h-screen sm:max-h-[94vh] overflow-hidden">
        <div class="p-10 text-center text-gray-400">Loading bill…</div></div>`;
      document.body.appendChild(this.root);
      this.onKey = e => { if (e.key === 'Escape' && !this.st.busy) this.close(); };
      document.addEventListener('keydown', this.onKey);
      try {
        const [methods, preview] = await Promise.all([loadMethods(), this.fetchPreview()]);
        this.methods = methods;
        this.preview = preview;
        this.st.includeService = methods.tax.service_charge_enabled;
        this.st.customerName = preview.customer_name || '';
        this.st.method = methods.methods[0] ? methods.methods[0].key : 'cash';
        if (preview.bill) {
          // Re-opening a bill that was already created: show it exactly as printed
          const b = preview.bill;
          this.st.issued = b;
          this.st.discountType = b.discount_type || null;
          this.st.discountValue = b.discount_value || 0;
          this.st.includeService = b.include_service_charge;
          this.st.customerName = b.customer_name || this.st.customerName;
          this.st.customerPan = b.customer_pan || '';
          this.st.showCustomer = !!b.customer_pan;
          this.preview = await this.fetchPreview();
        }
        this.render();
      } catch (e) {
        fail(e);
        this.close();
      }
    }

    close() {
      if (this.st.dyn && this.st.dyn.timer) clearInterval(this.st.dyn.timer);
      document.removeEventListener('keydown', this.onKey);
      this.root.remove();
      if (this.opts.onClose && !this.st.bill) this.opts.onClose();
    }

    fetchPreview() {
      return api('/api/billing/preview', {
        method: 'POST',
        body: {
          order_id: this.orderId,
          discount_type: this.st.discountType,
          discount_value: Number(this.st.discountValue) || 0,
          include_service_charge: this.st.includeService,
        },
      });
    }

    async refreshPreview() {
      try {
        this.preview = await this.fetchPreview();
      } catch (e) {
        fail(e);
        this.st.discountType = null;
        this.st.discountValue = 0;
        this.preview = await this.fetchPreview();
      }
    }

    get total() { return this.preview ? this.preview.grand_total : 0; }

    // ── Rendering ───────────────────────────────────────────────────────────
    render() {
      const box = this.root.firstElementChild;
      box.innerHTML = this.st.bill ? this.paidHtml() : this.formHtml();
      this.bind();
      this.updateComputed();
    }

    formHtml() {
      const p = this.preview;
      const tax = this.methods.tax;
      const st = this.st;
      const pendingNote = p.items.length === 0
        ? '<div class="bg-amber-50 text-amber-800 rounded-lg px-3 py-2 text-sm">This order has no items.</div>'
        : [p.pending_items > 0
            ? `<div class="bg-orange-50 text-orange-800 rounded-lg px-3 py-2 text-sm">🔔 ${p.pending_items} item(s) not sent to the kitchen yet — they will be sent when you confirm.</div>` : '',
           p.awaiting_accept > 0
            ? `<div class="bg-amber-50 text-amber-800 rounded-lg px-3 py-2 text-sm">⏳ The kitchen hasn't accepted ${p.awaiting_accept} item(s) yet.</div>` : '',
          ].join('');
      const discountChips = [
        ['None', null, 0], ['5%', 'percentage', 5], ['10%', 'percentage', 10], ['15%', 'percentage', 15],
      ].map(([text, type, value]) => {
        const on = st.discountType === type && (type === null || Number(st.discountValue) === value);
        return `<button data-disc="${type || ''}" data-val="${value}" class="px-3 py-2 rounded-lg text-sm font-medium border ${on ? 'bg-blue-600 text-white border-blue-600' : 'bg-white hover:bg-gray-50'}">${text}</button>`;
      }).join('');
      const customDisc = st.discountType && ![5, 10, 15].includes(Number(st.discountValue)) || st.discountType === 'flat';

      return `
      <div class="px-5 py-4 border-b flex items-center justify-between shrink-0">
        <div>
          <h2 class="text-xl font-bold text-gray-900">💳 Payment${p.table_number ? ' — Table ' + esc(p.table_number) : ''}</h2>
          <p class="text-sm text-gray-500">Order #${p.order_id}${st.issued
            ? ` · <span class="font-semibold text-purple-700">Bill ${esc(st.issued.bill_number)} issued — awaiting payment</span>`
            : ''}</p>
        </div>
        <button data-act="close" class="w-10 h-10 rounded-full hover:bg-gray-100 text-2xl text-gray-500" aria-label="Close">&times;</button>
      </div>

      <div class="flex-1 overflow-y-auto grid md:grid-cols-2 gap-0 md:divide-x">
        <!-- Bill summary -->
        <section class="p-5 space-y-4">
          ${pendingNote}
          <details class="group" ${p.items.length <= 6 ? 'open' : ''}>
            <summary class="cursor-pointer text-sm font-semibold text-gray-600 select-none">${p.items.length} item${p.items.length === 1 ? '' : 's'} <span class="text-gray-400 group-open:hidden">— show</span></summary>
            <ul class="mt-2 divide-y text-sm">
              ${p.items.map(i => `<li class="py-1.5 flex justify-between gap-3"><span>${i.quantity} × ${esc(i.name)}</span><span class="tabular-nums">${num(i.line_total)}</span></li>`).join('')}
            </ul>
          </details>

          <div>
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Discount</p>
            <div class="flex flex-wrap gap-2">
              ${discountChips}
              <button data-act="disc-custom" class="px-3 py-2 rounded-lg text-sm font-medium border ${customDisc ? 'bg-blue-600 text-white border-blue-600' : 'bg-white hover:bg-gray-50'}">${customDisc ? (st.discountType === 'flat' ? 'Rs ' + num(st.discountValue) : st.discountValue + '%') : 'Other…'}</button>
            </div>
          </div>

          ${tax.service_charge_enabled ? `
          <label class="flex items-center justify-between gap-3 bg-gray-50 rounded-xl px-4 py-3 cursor-pointer">
            <span class="text-sm font-medium text-gray-700">Service charge (${tax.service_charge_rate}%)</span>
            <input type="checkbox" data-act="service" class="w-5 h-5 accent-blue-600" ${st.includeService ? 'checked' : ''}>
          </label>` : ''}

          <div class="rounded-xl border p-4 space-y-1.5 text-sm" id="pay-totals"></div>

          <div>
            <button data-act="customer" class="text-sm text-blue-700 font-medium hover:underline">${st.showCustomer ? '− Hide' : '+ Add'} customer name / PAN (business bill)</button>
            <div class="${st.showCustomer ? '' : 'hidden'} grid grid-cols-2 gap-2 mt-2">
              <input data-field="customerName" value="${esc(st.customerName)}" placeholder="Customer name" class="border rounded-lg px-3 py-2.5 text-sm">
              <input data-field="customerPan" value="${esc(st.customerPan)}" placeholder="PAN (9 digits)" inputmode="numeric" maxlength="9" class="border rounded-lg px-3 py-2.5 text-sm">
            </div>
          </div>
        </section>

        <!-- Payment -->
        <section class="p-5 space-y-4 bg-gray-50/60">
          <div class="flex items-center justify-between">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">${st.split ? 'Split between methods' : 'Paid by'}</p>
            <button data-act="split" class="text-sm text-blue-700 font-medium hover:underline">${st.split ? 'Single method' : 'Split payment'}</button>
          </div>
          ${st.split ? this.splitHtml() : this.singleHtml()}
        </section>
      </div>

      <div class="border-t px-5 py-3 flex flex-wrap items-center gap-2 shrink-0 bg-white">
        <label class="flex items-center gap-2 text-sm text-gray-600 mr-auto cursor-pointer">
          <input type="checkbox" data-act="autoprint" class="w-4 h-4 accent-blue-600" ${localStorage.getItem(AUTO_PRINT_KEY) === '1' ? 'checked' : ''}>
          Print the bill automatically after payment
        </label>
        <button data-act="confirm" class="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white text-base font-bold">Confirm</button>
      </div>`;
    }

    methodButtons(selected, attr) {
      return `<div class="grid grid-cols-3 gap-2">
        ${this.methods.methods.map(m => `
          <button ${attr}="${m.key}" class="py-3 rounded-xl border-2 text-sm font-semibold flex flex-col items-center gap-1
            ${m.key === selected ? 'border-blue-600 bg-blue-50 text-blue-800' : 'border-gray-200 bg-white hover:border-gray-300 text-gray-700'}">
            <span class="text-2xl leading-none">${ICONS[m.key] || '💰'}</span>${esc(m.label)}
          </button>`).join('')}
      </div>`;
    }

    singleHtml() {
      const st = this.st;
      const m = this.methods.methods.find(x => x.key === st.method) || {};
      let detail = '';
      if (st.method === 'cash') {
        detail = `
          <label class="block text-sm font-medium text-gray-700">Cash received</label>
          <input data-field="tendered" type="number" inputmode="decimal" min="0" step="0.01" value="${esc(st.tendered)}"
            placeholder="${num(this.total)}" class="w-full border-2 rounded-xl px-4 py-3 text-2xl font-bold tabular-nums focus:outline-none focus:border-blue-500">
          <div class="flex flex-wrap gap-2">
            <button data-cash="exact" class="px-3 py-2 rounded-lg bg-white border text-sm font-semibold hover:bg-gray-50">Exact</button>
            ${quickCash(this.total).map(v => `<button data-cash="${v}" class="px-3 py-2 rounded-lg bg-white border text-sm font-semibold hover:bg-gray-50 tabular-nums">${num(v).replace('.00', '')}</button>`).join('')}
          </div>
          <div id="pay-change" class="rounded-xl px-4 py-3 text-center"></div>`;
      } else {
        const dynamic = st.method === 'qr' && this.methods.fonepay_dynamic;
        detail = `
          ${m.qr_image ? `
            <div class="bg-white rounded-xl border p-3 flex flex-col items-center gap-2">
              <img src="${esc(m.qr_image)}" alt="${esc(m.label)} QR" class="w-56 h-56 object-contain">
              <p class="text-sm text-gray-600">Ask the guest to scan and pay <b>${money(this.total)}</b></p>
            </div>` : (st.method !== 'card' ? `
            <p class="text-sm text-gray-500 bg-white border border-dashed rounded-xl p-3">
              Tip: upload your ${esc(m.label)} merchant QR in <b>Settings → Payments</b> to show it here for the guest.
            </p>` : '')}
          ${dynamic ? `
            <div id="pay-dyn" class="bg-white rounded-xl border p-3 text-center">
              <button data-act="dyn" class="px-4 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold">Generate FonePay QR (auto-confirms)</button>
            </div>` : ''}
          <label class="block text-sm font-medium text-gray-700">${st.method === 'card' ? 'Approval code / last 4 digits' : 'Transaction ID'} <span class="text-gray-400 font-normal">(optional)</span></label>
          <input data-field="reference" value="${esc(st.reference)}" class="w-full border rounded-xl px-3 py-2.5 text-sm" placeholder="Check the payment on your phone, then confirm">`;
      }
      return `${this.methodButtons(st.method, 'data-method')}<div class="space-y-3">${detail}</div>`;
    }

    splitHtml() {
      const options = sel => this.methods.methods.map(m =>
        `<option value="${m.key}" ${m.key === sel ? 'selected' : ''}>${ICONS[m.key] || ''} ${esc(m.label)}</option>`).join('');
      return `
        <div class="space-y-2">
          ${this.st.rows.map((r, i) => `
            <div class="flex items-center gap-2 bg-white border rounded-xl p-2">
              <select data-row="${i}" data-rf="method" class="border rounded-lg px-2 py-2.5 text-sm flex-1 min-w-0">${options(r.method)}</select>
              <input data-row="${i}" data-rf="amount" type="number" inputmode="decimal" min="0" step="0.01" value="${esc(r.amount)}" placeholder="0.00"
                class="w-28 border rounded-lg px-2 py-2.5 text-right font-semibold tabular-nums">
              <button data-rest="${i}" class="px-2 py-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-xs font-semibold" title="Fill the remaining amount">Rest</button>
              ${this.st.rows.length > 2 ? `<button data-del="${i}" class="w-8 h-8 text-red-500 hover:bg-red-50 rounded-lg" aria-label="Remove">✕</button>` : ''}
            </div>`).join('')}
          <button data-act="add-row" class="text-sm text-blue-700 font-medium hover:underline">+ Add another method</button>
          <div id="pay-remaining" class="rounded-xl px-4 py-3 text-center font-semibold"></div>
        </div>`;
    }

    paidHtml() {
      const b = this.st.bill;
      return `
        <div class="p-8 text-center overflow-y-auto">
          <div class="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4 text-4xl">✓</div>
          <h2 class="text-2xl font-extrabold text-green-700">Payment received</h2>
          <p class="text-gray-500 mt-1">Bill <b class="text-gray-800">${esc(b.bill_number)}</b> · ${money(b.grand_total)}</p>
          <p class="text-sm text-gray-500 mt-1">${b.payments.map(p => `${esc(p.label)} ${num(p.amount)}`).join(' + ')}</p>
          ${b.change ? `<div class="mt-5 inline-block bg-amber-100 text-amber-900 rounded-2xl px-8 py-4">
              <p class="text-sm font-semibold uppercase tracking-wide">Change to return</p>
              <p class="text-4xl font-extrabold tabular-nums">${money(b.change)}</p></div>` : ''}
          ${b.kot && b.kot.kot_number ? `<p class="text-sm text-orange-700 mt-4">🔔 ${b.kot.items_sent} unsent item(s) went to the kitchen as KOT #${b.kot.kot_number}</p>` : ''}
          <div class="flex flex-col sm:flex-row gap-3 justify-center mt-7">
            <button data-act="receipt" class="px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold">🖨 Print bill</button>
            <button data-act="done" class="px-8 py-3.5 rounded-xl border-2 font-semibold hover:bg-gray-50">Done</button>
          </div>
        </div>`;
    }

    // ── Live numbers (no re-render, so inputs keep focus) ───────────────────
    updateComputed() {
      if (this.st.bill) return;
      const p = this.preview;
      const tax = this.methods.tax;
      const totals = this.root.querySelector('#pay-totals');
      const row = (label, value, cls = '') => `<div class="flex justify-between ${cls}"><span>${label}</span><span class="tabular-nums">${value}</span></div>`;
      totals.innerHTML = [
        row('Subtotal', num(p.subtotal), 'text-gray-600'),
        p.discount_amount > 0 ? row(`Discount${p.discount_type === 'percentage' ? ` (${p.discount_value}%)` : ''}`, '−' + num(p.discount_amount), 'text-green-700') : '',
        p.service_charge > 0 ? row(`Service charge (${p.service_charge_rate}%)`, num(p.service_charge), 'text-gray-600') : '',
        tax.vat_enabled && p.vat_amount > 0 ? row('Taxable amount', num(p.taxable_amount), 'text-gray-600') : '',
        tax.vat_enabled && p.vat_amount > 0 ? row(`VAT (${p.vat_rate}%)`, num(p.vat_amount), 'text-gray-600') : '',
        `<div class="flex justify-between items-baseline border-t pt-2 mt-1"><span class="font-bold text-gray-900">Total</span>
           <span class="text-2xl font-extrabold text-gray-900 tabular-nums">${money(p.grand_total)}</span></div>`,
      ].join('');

      const confirmBtn = this.root.querySelector('[data-act=confirm]');
      let ok = p.items.length > 0 && !this.st.busy;
      if (this.st.split) {
        const paid = round2(this.st.rows.reduce((s, r) => s + (Number(r.amount) || 0), 0));
        const left = round2(this.total - paid);
        const box = this.root.querySelector('#pay-remaining');
        if (Math.abs(left) < 0.01) {
          box.className = 'rounded-xl px-4 py-3 text-center font-semibold bg-green-100 text-green-800';
          box.textContent = 'Fully covered ✓';
        } else if (left > 0) {
          box.className = 'rounded-xl px-4 py-3 text-center font-semibold bg-amber-100 text-amber-900';
          box.textContent = `Remaining: ${money(left)}`;
          ok = false;
        } else {
          box.className = 'rounded-xl px-4 py-3 text-center font-semibold bg-red-100 text-red-800';
          box.textContent = `Over by ${money(-left)} — reduce an amount`;
          ok = false;
        }
      } else if (this.st.method === 'cash') {
        const tendered = Number(this.st.tendered);
        const box = this.root.querySelector('#pay-change');
        if (!this.st.tendered) {
          box.className = 'rounded-xl px-4 py-3 text-center text-sm text-gray-500 bg-white border';
          box.textContent = 'Leave empty if the guest paid the exact amount';
        } else if (tendered + 0.005 < this.total) {
          box.className = 'rounded-xl px-4 py-3 text-center font-semibold bg-red-100 text-red-800';
          box.textContent = `Short by ${money(this.total - tendered)}`;
          ok = false;
        } else {
          box.className = 'rounded-xl px-4 py-3 text-center bg-green-100 text-green-900';
          box.innerHTML = `<span class="text-sm font-semibold">Change</span>
            <span class="block text-3xl font-extrabold tabular-nums">${money(tendered - this.total)}</span>`;
        }
      }
      confirmBtn.disabled = !ok;
      confirmBtn.textContent = this.st.busy ? 'Please wait…' : `💳 Confirm payment ${money(this.total)}`;
    }

    // ── Events ──────────────────────────────────────────────────────────────
    bind() {
      const $ = sel => this.root.querySelector(sel);
      const $$ = sel => this.root.querySelectorAll(sel);
      const on = (sel, fn) => { const el = $(sel); if (el) el.onclick = fn; };

      on('[data-act=close]', () => this.close());
      on('[data-act=done]', () => { this.close(); this.opts.onPaid && this.opts.onPaid(this.st.bill); });
      on('[data-act=receipt]', () => POS.printReceipt(this.st.bill.id));
      if (this.st.bill) return;

      $$('[data-disc]').forEach(b => b.onclick = async () => {
        this.st.discountType = b.dataset.disc || null;
        this.st.discountValue = Number(b.dataset.val) || 0;
        await this.refreshPreview();
        this.render();
      });
      on('[data-act=disc-custom]', async () => {
        const v = await POS.prompt('Discount', {
          message: 'Enter a percentage like 12% or a rupee amount like 150',
          placeholder: 'e.g. 12% or 150', chips: ['20%', '25%', '50', '100'], okText: 'Apply',
        });
        if (v === null || v === '') return;
        const isPct = v.includes('%');
        const n = parseFloat(v.replace(/[^\d.]/g, ''));
        if (!(n >= 0)) { toast('Enter a number', { type: 'error' }); return; }
        this.st.discountType = isPct ? 'percentage' : 'flat';
        this.st.discountValue = n;
        await this.refreshPreview();
        this.render();
      });
      const svc = $('[data-act=service]');
      if (svc) svc.onchange = async () => {
        this.st.includeService = svc.checked;
        await this.refreshPreview();
        this.render();
      };
      on('[data-act=customer]', () => { this.st.showCustomer = !this.st.showCustomer; this.render(); });
      on('[data-act=split]', () => {
        this.st.split = !this.st.split;
        if (this.st.split && this.st.rows.length === 0) {
          const keys = this.methods.methods.map(m => m.key);
          this.st.rows = [
            { method: keys.includes('cash') ? 'cash' : keys[0], amount: '' },
            { method: keys.find(k => k !== 'cash') || keys[0], amount: '' },
          ];
        }
        this.render();
      });
      on('[data-act=add-row]', () => {
        this.st.rows.push({ method: this.methods.methods[0].key, amount: '' });
        this.render();
      });
      const ap = $('[data-act=autoprint]');
      if (ap) ap.onchange = () => localStorage.setItem(AUTO_PRINT_KEY, ap.checked ? '1' : '0');
      on('[data-act=confirm]', () => this.confirm());
      on('[data-act=dyn]', () => this.startDynamicQr());

      $$('[data-method]').forEach(b => b.onclick = () => {
        this.st.method = b.dataset.method;
        this.st.reference = '';
        this.render();
        const input = $('[data-field=tendered]');
        if (input) input.focus();
      });
      $$('[data-cash]').forEach(b => b.onclick = () => {
        this.st.tendered = b.dataset.cash === 'exact' ? String(this.total) : b.dataset.cash;
        $('[data-field=tendered]').value = this.st.tendered;
        this.updateComputed();
      });
      $$('[data-field]').forEach(input => input.oninput = () => {
        this.st[input.dataset.field] = input.value;
        this.updateComputed();
      });
      $$('[data-rf]').forEach(el => {
        const handler = () => {
          this.st.rows[Number(el.dataset.row)][el.dataset.rf] = el.value;
          this.updateComputed();
        };
        el.oninput = handler;
        el.onchange = handler;
      });
      $$('[data-rest]').forEach(b => b.onclick = () => {
        const i = Number(b.dataset.rest);
        const others = this.st.rows.reduce((s, r, j) => s + (j === i ? 0 : Number(r.amount) || 0), 0);
        this.st.rows[i].amount = String(Math.max(0, round2(this.total - others)));
        this.render();
      });
      $$('[data-del]').forEach(b => b.onclick = () => {
        this.st.rows.splice(Number(b.dataset.del), 1);
        this.render();
      });

      if (!this.st.split && this.st.method === 'cash') {
        const input = $('[data-field=tendered]');
        if (input && window.matchMedia('(pointer: fine)').matches) input.focus();
      }
    }

    payload() {
      const base = {
        order_id: this.orderId,
        discount_type: this.st.discountType,
        discount_value: Number(this.st.discountValue) || 0,
        include_service_charge: this.st.includeService,
        customer_name: this.st.customerName.trim() || null,
        customer_pan: this.st.customerPan.trim() || null,
      };
      if (this.st.split) {
        base.payments = this.st.rows
          .filter(r => Number(r.amount) > 0)
          .map(r => ({ method: r.method, amount: round2(r.amount) }));
      } else {
        const cash = this.st.method === 'cash';
        base.payments = [{
          method: this.st.method,
          amount: this.total,
          tendered: cash && this.st.tendered ? round2(this.st.tendered) : null,
          reference: cash ? null : (this.st.reference.trim() || null),
        }];
      }
      return base;
    }

    billFields() {
      return {
        discount_type: this.st.discountType || '',
        discount_value: Number(this.st.discountValue) || 0,
        include_service_charge: this.st.includeService,
        customer_name: this.st.customerName.trim(),
        customer_pan: this.st.customerPan.trim(),
      };
    }

    /** The order's bill with the dialog's current discount/service/customer applied. */
    async ensureBill() {
      const update = id => api(`/api/billing/bills/${id}/update`, { method: 'PATCH', body: this.billFields() });
      if (this.st.issued) return update(this.st.issued.id);
      try {
        const f = this.billFields();
        return await api('/api/billing/bills', { method: 'POST', body: {
          order_id: this.orderId, ...f, discount_type: f.discount_type || null,
          customer_name: f.customer_name || null, customer_pan: f.customer_pan || null,
        }});
      } catch (e) {
        const existing = e.status === 409 && e.headers && e.headers.get('X-Bill-Id');
        if (!existing) throw e;
        return update(Number(existing));            // someone else created it a moment ago
      }
    }

    async confirm() {
      if (this.st.busy) return;
      this.st.busy = true;
      this.updateComputed();
      try {
        const bill = await api('/api/billing/checkout', { method: 'POST', body: this.payload() });
        this.paid(bill);
      } catch (e) {
        this.st.busy = false;
        fail(e);
        if (e.status === 400 && /bill is/i.test(e.message)) {   // totals moved underneath us
          await this.refreshPreview();
          this.render();
        } else {
          this.updateComputed();
        }
      }
    }

    paid(bill) {
      if (this.st.dyn && this.st.dyn.timer) clearInterval(this.st.dyn.timer);
      this.st.busy = false;
      this.st.bill = bill;
      this.render();
      if (localStorage.getItem(AUTO_PRINT_KEY) === '1') POS.printReceipt(bill.id);
      document.dispatchEvent(new CustomEvent('pos:paid', { detail: bill }));
    }

    // ── FonePay dynamic QR (only when real merchant credentials are set) ────
    async startDynamicQr() {
      const box = this.root.querySelector('#pay-dyn');
      box.innerHTML = '<p class="text-sm text-gray-500 animate-pulse">Connecting to FonePay…</p>';
      try {
        const billId = (await this.ensureBill()).id;
        const qr = await api(`/api/billing/bills/${billId}/fonepay-qr`, { method: 'POST' });
        const src = qr.qr_image
          ? (qr.qr_image.startsWith('data:') ? qr.qr_image : `data:image/png;base64,${qr.qr_image}`)
          : `/api/qr.png?data=${encodeURIComponent(qr.qr_data)}`;
        box.innerHTML = `<img src="${esc(src)}" class="w-52 h-52 mx-auto" alt="FonePay QR">
          <p class="font-bold mt-2">${money(qr.amount)}</p>
          <p class="text-xs text-gray-500 animate-pulse">Waiting for payment… this screen updates by itself</p>`;
        this.st.dyn = {
          billId,
          timer: setInterval(async () => {
            try {
              const s = await api(`/api/billing/bills/${billId}/payment-status`);
              if (s.payment_status === 'paid') this.paid(await api(`/api/billing/bills/${billId}`));
            } catch { /* keep polling */ }
          }, 3000),
        };
      } catch (e) {
        box.innerHTML = `<p class="text-sm text-red-600">${esc(e.message)}</p>`;
      }
    }
  }

  window.PaymentDialog = PaymentDialog;
})();
