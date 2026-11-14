const webApp = window.Telegram?.WebApp;
const headers = () => ({'Content-Type': 'application/json', ...(webApp?.initData ? {Authorization: `tma ${webApp.initData}`} : {})});
let tenants = [], filter = 'ALL';
const api = (path, options = {}) => fetch(`/api${path}`, {...options, headers: {...headers(), ...(options.headers || {})}}).then(async response => {
  if (!response.ok) throw new Error(await response.text());
  return response.json();
});
function render() {
  const counts = Object.fromEntries(['OVERDUE','DUE_SOON','PAID'].map(status => [status, tenants.filter(t => t.status === status).length]));
  document.querySelector('#filters').innerHTML = [['ALL','All'],['OVERDUE',`Overdue (${counts.OVERDUE})`],['DUE_SOON',`Due Soon (${counts.DUE_SOON})`],['PAID',`Paid (${counts.PAID})`]].map(([key,label]) => `<button data-filter="${key}" class="rounded px-3 py-1 text-sm ${filter===key?'bg-slate-900 text-white':'bg-white'}">${label}</button>`).join('');
  document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => { filter = button.dataset.filter; render(); });
  document.querySelector('#tenants').innerHTML = tenants.filter(t => filter === 'ALL' || t.status === filter).map(t => `<article class="rounded-lg bg-white p-4 shadow"><div class="flex justify-between font-semibold"><span>Room ${t.room_number}</span><span>${t.status}</span></div><p>SSID: ${t.ssid}</p><p>MACs: ${t.mac_addresses.join(', ')}</p><p>Last payment: ${t.last_payment_date}</p><p>Next due: ${t.next_due_date}</p><button class="mark-paid mt-2 rounded bg-green-600 px-3 py-1 text-white" data-id="${t.id}">Mark Paid</button></article>`).join('');
  document.querySelectorAll('.mark-paid').forEach(button => button.onclick = async () => { await api(`/tenants/${button.dataset.id}/pay`, {method:'POST', body: JSON.stringify({})}); await load(); });
}
async function load() { tenants = await api('/tenants'); render(); }
document.querySelector('#report').onclick = () => api('/report/trigger', {method:'POST'});
webApp?.ready(); load().catch(error => { document.querySelector('#tenants').textContent = error.message; });
