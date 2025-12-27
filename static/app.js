/* global io */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let STATE = null;
let SOCKET = null;

function setStatus(msg){
  const el = $('#status');
  if (!el) return;
  el.textContent = msg;
}

function fmtNum(n){
  if (n === null || n === undefined) return '-';
  return (Math.round(n * 1000) / 1000).toString();
}

function groupDesserts(desserts){
  const byPid = {};
  for (const d of desserts){ byPid[d.participant_id] = d; }
  return byPid;
}

function render(){
  if (!STATE) return;
  $('#competitionName').textContent = STATE.settings.competition_name || 'Holiday Bakeoff';

  // Criteria UI
  const criteria = STATE.settings.criteria || [];
  const criteriaWrap = $('#criteriaWrap');
  criteriaWrap.innerHTML = '';
  for (const c of criteria){
    const row = document.createElement('div');
    row.className = 'criterion';
    row.innerHTML = `
      <label>
        <div class="crit-head">
          <span class="crit-label">${c.label}</span>
          <span class="crit-max">0–${c.max}</span>
        </div>
        <input type="range" min="0" max="${c.max}" step="1" value="0" data-ckey="${c.key}" />
        <div class="crit-val" id="val-${c.key}">0</div>
      </label>
    `;
    criteriaWrap.appendChild(row);
  }
  // Range live values
  $$('input[type=range][data-ckey]').forEach((rng) => {
    const key = rng.dataset.ckey;
    const valEl = $(`#val-${key}`);
    const upd = () => { valEl.textContent = rng.value; };
    rng.addEventListener('input', upd);
    upd();
  });

  // Participant dropdown
  const sel = $('#participantSelect');
  sel.innerHTML = '<option value="">Select a baker…</option>';
  const activeParticipants = (STATE.participants || []).filter(p => p.active);
  for (const p of activeParticipants){
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    sel.appendChild(opt);
  }

  // Leaderboard
  const dessertsByPid = groupDesserts(STATE.desserts || []);
  const lb = $('#leaderboardBody');
  lb.innerHTML = '';
  for (const row of (STATE.leaderboard || [])){
    const d = dessertsByPid[row.participant_id];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="rank">#</td>
      <td>
        <div class="who">
          <div class="name">${row.name}${row.active ? '' : ' (inactive)'}</div>
          <div class="sub">${d ? (d.dessert_name + (d.category ? ' • ' + d.category : '')) : 'Dessert not entered yet'}</div>
        </div>
      </td>
      <td class="num">${row.num_scores || 0}</td>
      <td class="num"><b>${fmtNum(row.weighted_total || 0)}</b></td>
    `;
    lb.appendChild(tr);
  }
  // Fill ranks
  Array.from(lb.querySelectorAll('tr')).forEach((tr, i) => {
    const td = tr.querySelector('td.rank');
    if (td) td.textContent = `#${i+1}`;
  });

  // Recent scores
  const recent = $('#recentScores');
  recent.innerHTML = '';
  const recentList = (STATE.scores || []).slice(0, 10);
  for (const s of recentList){
    const item = document.createElement('div');
    item.className = 'log-item';
    const total = Object.values(s.criteria || {}).reduce((a,b)=>a+Number(b||0),0);
    item.innerHTML = `<div><b>${s.participant_name}</b> scored by <b>${s.judge_name}</b></div><div class="muted">Total: ${fmtNum(total)} • ${new Date(s.created_at).toLocaleString()}</div>`;
    recent.appendChild(item);
  }

  // Voting status
  const votingOpen = !!STATE.settings.voting_open;
  const pill = $('#votingPill');
  pill.textContent = votingOpen ? 'Voting Open' : 'Voting Closed';
  pill.className = 'pill ' + (votingOpen ? 'pill-open' : 'pill-closed');

  setStatus('');
}

async function fetchState(){
  const res = await fetch('/api/state');
  STATE = await res.json();
  render();
}

function connectSocket(){
  SOCKET = io({ transports: ['websocket', 'polling'] });
  SOCKET.on('connect', () => setStatus('Connected ✅'));
  SOCKET.on('disconnect', () => setStatus('Disconnected… refreshing'));
  SOCKET.on('state_update', (payload) => {
    STATE = payload;
    render();
  });
}

async function submitScore(ev){
  ev.preventDefault();
  const judge_name = ($('#judgeName').value || '').trim();
  const participant_id = Number($('#participantSelect').value || 0);
  const comment = ($('#comment').value || '').trim();
  const criteria = {};
  $$('input[type=range][data-ckey]').forEach((rng) => {
    criteria[rng.dataset.ckey] = Number(rng.value);
  });

  const res = await fetch('/api/scores', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ judge_name, participant_id, criteria, comment }),
  });
  const data = await res.json();
  if (!res.ok){
    alert(data.error || 'Could not submit score');
    return;
  }
  // reset form
  $$('input[type=range][data-ckey]').forEach((rng) => { rng.value = 0; rng.dispatchEvent(new Event('input')); });
  $('#comment').value = '';
  alert('Score submitted! 🎁');
}

function bindTabs(){
  $$('.tab').forEach((t) => t.addEventListener('click', () => {
    $$('.tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    const target = t.dataset.tab;
    $$('.panel').forEach(p => p.classList.add('hidden'));
    $(`#panel-${target}`).classList.remove('hidden');
  }));
}

window.addEventListener('DOMContentLoaded', async () => {
  bindTabs();
  $('#scoreForm').addEventListener('submit', submitScore);
  await fetchState();
  connectSocket();
});
