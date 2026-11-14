const webApp = window.Telegram?.WebApp;
const state = { tenants: [], filter: 'ALL', query: '', editingId: null, payingId: null };
const $ = (selector) => document.querySelector(selector);
const today = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Phnom_Penh'}).format(new Date());
const headers = () => ({'Content-Type': 'application/json', ...(webApp?.initData ? {Authorization: `tma ${webApp.initData}`} : {})});

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {...options, headers: {...headers(), ...(options.headers || {})}});
  if (!response.ok) throw new Error(await response.text());
  return response.status === 204 ? null : response.json();
}
function showMessage(text, error = true) {
  const element = $('#message'); element.textContent = text; element.className = `mb-3 border px-3 py-2 text-sm ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`;
  clearTimeout(showMessage.timer); showMessage.timer = setTimeout(() => element.classList.add('hidden'), 4000);
}
function openModal(id) { $(id).classList.replace('hidden', 'flex'); }
function closeModal(id) { $(id).classList.replace('flex', 'hidden'); }
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char])); }
function formatMacInput(rawValue) {
  const hexOnly = String(rawValue || '').replace(/[^0-9a-fA-F]/g, '').toUpperCase().slice(0, 12);
  return (hexOnly.match(/.{1,2}/g) || []).join(':');
}
function isValidMac(macValue) { return /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(macValue); }
function addMacInputRow(value = '') {
  const row = document.createElement('div'); row.className = 'flex gap-2';
  row.innerHTML = `<input value="${escapeHtml(formatMacInput(value))}" maxlength="17" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="AABBCCDDEEFF or AA:BB:CC:DD:EE:FF" class="mac-input min-w-0 flex-1 rounded border border-neutral-300 px-3 py-2 font-mono text-sm uppercase"><button type="button" class="remove-mac rounded border border-neutral-300 px-2 text-sm">×</button>`;
  const input = row.querySelector('.mac-input');
  input.addEventListener('input', (event) => { event.target.value = formatMacInput(event.target.value); event.target.classList.remove('border-red-500'); });
  input.addEventListener('paste', () => setTimeout(() => { input.value = formatMacInput(input.value); }, 0));
  row.querySelector('.remove-mac').onclick = () => row.remove(); $('#mac-inputs-container').append(row);
}
function openCreateModal() {
  state.editingId = null; $('#room-form').reset(); $('#room-modal-title').textContent = 'Add Room'; $('#due-day').value = new Date().toLocaleString('en-US', {timeZone: 'Asia/Phnom_Penh', day: 'numeric'}); $('#last-payment-date').value = today(); $('#mac-inputs-container').replaceChildren(); addMacInputRow(); openModal('#room-modal');
}
function openEditModal(id) {
  const tenant = state.tenants.find((item) => item.id === id); if (!tenant) return;
  state.editingId = id; $('#room-modal-title').textContent = `Edit Room ${tenant.room_number}`; $('#room-number').value = tenant.room_number; $('#ssid').value = tenant.ssid; $('#due-day').value = tenant.due_day; $('#last-payment-date').value = tenant.last_payment_date; $('#mac-inputs-container').replaceChildren(); tenant.devices.forEach((device) => addMacInputRow(device.mac_address)); openModal('#room-modal');
}
async function saveTenant(event) {
  event.preventDefault();
  const macInputs = [...document.querySelectorAll('.mac-input')];
  const macAddresses = macInputs.map((input) => { input.value = formatMacInput(input.value); return input.value; }).filter(Boolean);
  const invalidMac = macInputs.find((input) => input.value && !isValidMac(input.value));
  if (invalidMac) { invalidMac.classList.add('border-red-500'); showMessage('MAC address must be exactly 12 hex characters (0-9, A-F).'); invalidMac.focus(); return; }
  const body = {room_number: $('#room-number').value.trim(), ssid: $('#ssid').value.trim(), due_day: Number($('#due-day').value), last_payment_date: $('#last-payment-date').value, mac_addresses: macAddresses};
  try { await api(state.editingId ? `/tenants/${state.editingId}` : '/tenants', {method: state.editingId ? 'PUT' : 'POST', body: JSON.stringify(body)}); closeModal('#room-modal'); showMessage('Room saved', false); await fetchTenants(); } catch (error) { showMessage(error.message); }
}
function openPayModal(id) {
  const tenant = state.tenants.find((item) => item.id === id); if (!tenant) return;
  state.payingId = id; $('#pay-modal-title').textContent = `Record payment for Room ${tenant.room_number}`; $('#pay-date-input').value = today(); $('#pay-note').textContent = `Next due date will remain anchored to day ${tenant.due_day} of next month.`; openModal('#pay-modal');
}
async function confirmMarkPaid(event) {
  event.preventDefault(); try { await api(`/tenants/${state.payingId}/pay`, {method: 'POST', body: JSON.stringify({payment_date: $('#pay-date-input').value})}); closeModal('#pay-modal'); showMessage('Payment recorded', false); await fetchTenants(); } catch (error) { showMessage(error.message); }
}
async function deleteTenant(id) {
  const tenant = state.tenants.find((item) => item.id === id); if (!tenant || !window.confirm(`Delete Room ${tenant.room_number}?`)) return;
  try { await api(`/tenants/${id}`, {method: 'DELETE'}); showMessage('Room deleted', false); await fetchTenants(); } catch (error) { showMessage(error.message); }
}
function renderTenants() {
  const counts = Object.fromEntries(['ALL', 'OVERDUE', 'DUE_SOON', 'PAID'].map((status) => [status, status === 'ALL' ? state.tenants.length : state.tenants.filter((tenant) => tenant.status === status).length]));
  $('#filters').innerHTML = [['ALL', 'All'], ['OVERDUE', 'Overdue'], ['DUE_SOON', 'Due Soon'], ['PAID', 'Paid']].map(([key, label]) => `<button data-filter="${key}" class="rounded px-3 py-1.5 text-xs ${state.filter === key ? 'bg-neutral-900 text-white' : 'border border-neutral-200 bg-white text-neutral-700'}">${label} (${counts[key]})</button>`).join('');
  document.querySelectorAll('[data-filter]').forEach((button) => button.onclick = () => { state.filter = button.dataset.filter; renderTenants(); });
  const query = state.query.toLowerCase(); const visible = state.tenants.filter((tenant) => (state.filter === 'ALL' || tenant.status === state.filter) && `${tenant.room_number} ${tenant.ssid} ${tenant.devices.map((device) => device.mac_address).join(' ')}`.toLowerCase().includes(query));
  if (!state.tenants.length) { $('#tenants').innerHTML = '<div class="py-16 text-center"><p class="text-sm text-neutral-500">No rooms yet.</p><button id="btn-add-first" class="mt-3 rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm">+ Add First Room</button></div>'; $('#btn-add-first').onclick = openCreateModal; return; }
  $('#tenants').innerHTML = visible.length ? visible.map((tenant) => {
    const statusClass = {OVERDUE: 'border-red-200 bg-red-50 text-red-700', DUE_SOON: 'border-amber-200 bg-amber-50 text-amber-800', PAID: 'border-emerald-200 bg-emerald-50 text-emerald-700'}[tenant.status];
    const statusText = tenant.status === 'OVERDUE' ? `OVERDUE: ${Math.abs(tenant.days_until_due)}d` : tenant.status === 'DUE_SOON' ? `DUE IN ${tenant.days_until_due}d` : 'PAID';
    return `<article class="border border-neutral-200 bg-white p-4"><div class="flex items-start justify-between gap-2"><h2 class="font-mono text-base font-semibold">Room ${escapeHtml(tenant.room_number)} <span class="text-xs font-normal text-neutral-500">· Due ${tenant.due_day}</span></h2><span class="rounded border px-2 py-1 text-xs ${statusClass}">${statusText}</span></div><div class="mt-2 grid grid-cols-2 gap-2 text-xs text-neutral-600"><div>SSID: <span class="font-mono text-neutral-900">${escapeHtml(tenant.ssid)}</span></div><div>Due Day: <span class="font-mono text-neutral-900">Every ${tenant.due_day}</span></div><div>Last Paid: <span class="font-mono text-neutral-900">${tenant.last_payment_date}</span></div><div>Next Due: <span class="font-mono font-semibold text-neutral-900">${tenant.next_due_date}</span></div></div>${tenant.late_days_remark ? `<p class="mt-2 text-xs text-neutral-500">Paid ${tenant.late_days_remark}d late</p>` : ''}<div class="mt-3 flex flex-wrap gap-1.5">${tenant.devices.map((device) => `<button type="button" data-copy-mac="${device.mac_address}" title="Click to copy MAC address" class="mac-copy-btn inline-flex items-center gap-1 rounded border border-neutral-300 bg-neutral-100 px-2 py-1 font-mono text-xs text-neutral-900 hover:bg-neutral-200">${device.mac_address}</button>`).join('')}</div><footer class="mt-3 flex items-center justify-between border-t border-neutral-100 pt-2.5"><button data-pay="${tenant.id}" class="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white">Mark Paid</button><div class="flex gap-2"><button data-edit="${tenant.id}" class="rounded border border-neutral-300 px-2.5 py-1 text-xs">Edit</button><button data-delete="${tenant.id}" class="rounded border border-red-200 px-2.5 py-1 text-xs text-red-600">Delete</button></div></footer></article>`;
  }).join('') : '<p class="py-8 text-center text-sm text-neutral-500">No matching rooms.</p>';
  document.querySelectorAll('[data-pay]').forEach((button) => button.onclick = () => openPayModal(Number(button.dataset.pay)));
  document.querySelectorAll('[data-edit]').forEach((button) => button.onclick = () => openEditModal(Number(button.dataset.edit)));
  document.querySelectorAll('[data-delete]').forEach((button) => button.onclick = () => deleteTenant(Number(button.dataset.delete)));
  document.querySelectorAll('[data-copy-mac]').forEach((button) => button.onclick = () => copyMacToClipboard(button.dataset.copyMac, button));
}
async function copyMacToClipboard(macAddress, buttonElement) {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(macAddress);
    else throw new Error('Clipboard API unavailable');
  } catch {
    const textarea = document.createElement('textarea');
    textarea.value = macAddress; textarea.style.position = 'fixed'; textarea.style.opacity = '0';
    document.body.append(textarea); textarea.select(); document.execCommand('copy'); textarea.remove();
  }
  const original = buttonElement.textContent;
  buttonElement.textContent = 'Copied!'; buttonElement.classList.add('bg-neutral-900', 'text-white', 'border-neutral-900');
  setTimeout(() => { buttonElement.textContent = original; buttonElement.classList.remove('bg-neutral-900', 'text-white', 'border-neutral-900'); }, 1000);
}
async function fetchTenants() { state.tenants = await api('/tenants'); renderTenants(); }
async function triggerGroupReport() { try { await api('/report/trigger', {method: 'POST'}); showMessage('Report sent', false); } catch (error) { showMessage(error.message); } }
$('#today').textContent = today(); $('#btn-add-room').onclick = openCreateModal; $('#btn-report').onclick = triggerGroupReport; $('#room-form').onsubmit = saveTenant; $('#pay-form').onsubmit = confirmMarkPaid; $('#btn-add-mac').onclick = () => addMacInputRow(); $('#search').oninput = (event) => { state.query = event.target.value; renderTenants(); }; document.querySelectorAll('[data-close]').forEach((button) => button.onclick = () => closeModal(`#${button.dataset.close}`)); webApp?.ready(); fetchTenants().catch((error) => showMessage(error.message));
