const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let STATE = null;

function toast(msg){
  const el = $('#adminToast');
  if(!el) return alert(msg);
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'), 2200);
}

async function api(path, opts={}){
  const res = await fetch(path, {
    headers: {'Content-Type': 'application/json'},
    credentials: 'same-origin',
    ...opts,
  });
  let data = null;
  try{ data = await res.json(); }catch(e){/* ignore */}
  if(!res.ok){
    const msg = (data && data.error) ? data.error : (res.statusText || 'Request failed');
    throw new Error(msg);
  }
  return data;
}

function renderParticipants(){
  const tbody = $('#participantsTbody');
  tbody.innerHTML = '';
  const list = STATE.participants || [];
  for(const p of list){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${p.active ? '✅' : '❌'}</td>
      <td class="right">
        <button class="btn small" data-act="toggle" data-id="${p.id}">${p.active ? 'Deactivate' : 'Activate'}</button>
        <button class="btn small danger" data-act="delete" data-id="${p.id}">Delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
}

function renderDesserts(){
  const tbody = $('#dessertsTbody');
  tbody.innerHTML = '';
  const desserts = STATE.desserts || [];
  const byPid = new Map(desserts.map(d => [d.participant_id, d]));
  const list = (STATE.participants || []).slice().sort((a,b)=>a.name.localeCompare(b.name));
  for(const p of list){
    const d = byPid.get(p.id);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name}${p.active ? '' : ' <span class="pill dim">inactive</span>'}</td>
      <td><input class="in" data-k="dessert_name" data-id="${p.id}" value="${d ? escapeHtml(d.dessert_name) : ''}" placeholder="e.g., Gingerbread Cheesecake" /></td>
      <td><input class="in" data-k="category" data-id="${p.id}" value="${d ? escapeHtml(d.category||'') : ''}" placeholder="Cookie / Cake / Pie / ..." /></td>
      <td><input class="in" data-k="description" data-id="${p.id}" value="${d ? escapeHtml(d.description||'') : ''}" placeholder="short description" /></td>
      <td class="right"><button class="btn small" data-act="saveDessert" data-id="${p.id}">Save</button></td>
    `;
    tbody.appendChild(tr);
  }
}

function escapeHtml(s){
  return (s||'')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
}

function renderSettings(){
  const s = STATE.settings || {};
  $('#competitionName').value = s.competition_name || '2025 Holiday Bakeoff';
  $('#votingOpen').checked = !!s.voting_open;
  $('#multiScore').checked = !!s.allow_multiple_scores_per_judge;
  $('#criteriaJson').value = JSON.stringify(s.criteria || [], null, 2);
}

async function load(){
  const data = await api('/api/state');
  STATE = data;
  renderParticipants();
  renderDesserts();
  renderSettings();
  renderEvents();
}

function renderEvents(){
  const el = $('#eventsList');
  el.innerHTML = '';
  const events = STATE.events || [];
  for(const e of events){
    const li = document.createElement('li');
    li.textContent = `${e.created_at} • ${e.type}`;
    el.appendChild(li);
  }
}

async function main(){
  await load();

  $('#addParticipantBtn').addEventListener('click', async ()=>{
    const name = $('#newParticipantName').value.trim();
    if(!name) return toast('Enter a name.');
    await api('/api/admin/participants', {method:'POST', body: JSON.stringify({name})});
    $('#newParticipantName').value = '';
    toast('Participant added.');
    await load();
  });

  $('#participantsTbody').addEventListener('click', async (e)=>{
    const btn = e.target.closest('button');
    if(!btn) return;
    const id = parseInt(btn.dataset.id, 10);
    const act = btn.dataset.act;
    if(act==='toggle'){
      const p = (STATE.participants||[]).find(x=>x.id===id);
      await api(`/api/admin/participants/${id}`, {method:'PATCH', body: JSON.stringify({active: !p.active})});
      toast('Updated.');
      await load();
    }
    if(act==='delete'){
      if(!confirm('Delete participant (and their dessert + scores)?')) return;
      await api(`/api/admin/participants/${id}`, {method:'DELETE'});
      toast('Deleted.');
      await load();
    }
  });

  $('#dessertsTbody').addEventListener('click', async (e)=>{
    const btn = e.target.closest('button');
    if(!btn) return;
    if(btn.dataset.act !== 'saveDessert') return;
    const pid = parseInt(btn.dataset.id, 10);
    const inputs = $$(
      `#dessertsTbody input[data-id="${pid}"]`
    );
    const payload = {participant_id: pid};
    for(const inp of inputs){
      payload[inp.dataset.k] = inp.value;
    }
    await api('/api/admin/desserts', {method:'POST', body: JSON.stringify(payload)});
    toast('Dessert saved.');
    await load();
  });

  $('#saveSettingsBtn').addEventListener('click', async ()=>{
    let criteria = [];
    try{ criteria = JSON.parse($('#criteriaJson').value); }catch(err){
      return toast('Criteria JSON is invalid.');
    }
    const payload = {
      competition_name: $('#competitionName').value.trim(),
      voting_open: $('#votingOpen').checked,
      allow_multiple_scores_per_judge: $('#multiScore').checked,
      criteria,
    };
    await api('/api/admin/settings', {method:'POST', body: JSON.stringify(payload)});
    toast('Settings saved.');
    await load();
  });

  $('#exportBtn').addEventListener('click', async ()=>{
    window.location.href = '/api/admin/export';
  });

  $('#backupBtn').addEventListener('click', async ()=>{
    const data = await api('/api/admin/backup', {method:'POST'});
    toast(`Backup saved: ${data.file}`);
    await load();
  });

  $('#importBtn').addEventListener('click', async ()=>{
    const file = $('#importFile').files[0];
    if(!file) return toast('Choose a JSON export file.');
    const mode = $('#importMode').value;
    const txt = await file.text();
    let payload;
    try{ payload = JSON.parse(txt); }catch(err){ return toast('Invalid JSON.'); }
    await api('/api/admin/import', {method:'POST', body: JSON.stringify({mode, payload})});
    toast('Imported.');
    await load();
  });

  $('#resetBtn').addEventListener('click', async ()=>{
    if(!confirm('This wipes ALL data. Continue?')) return;
    await api('/api/admin/reset', {method:'POST'});
    toast('Reset complete.');
    await load();
  });

  $('#aiBtn').addEventListener('click', async ()=>{
    const out = $('#aiOut');
    out.textContent = 'Generating...';
    try{
      const data = await api('/api/admin/ai/commentary', {method:'POST'});
      out.textContent = data.text;
    }catch(err){
      out.textContent = `AI disabled or error: ${err.message}`;
    }
  });
}

main().catch(err=>{
  console.error(err);
  toast(err.message || 'Error');
});
