const root = document.createElement('div');
root.className = 'nara-office';
root.innerHTML = `
  <header><div><span class="eyebrow">MISSION CONTROL</span><h1>Nara Office</h1></div>
    <div class="live"><i></i><span>estado real</span></div></header>
  <section class="metrics" id="metrics"></section>
  <main><section class="floor"><div class="section-title"><h2>Missões e equipe</h2><span id="updated"></span></div>
    <div class="missions" id="missions"></div></section>
    <aside><div class="panel"><h2>Lacunas</h2><div id="gaps"></div></div>
      <div class="panel"><h2>Frota</h2><div id="fleet"></div></div>
      <div class="panel"><h2>Laboratórios</h2><div id="labs"></div></div>
      <div class="panel"><h2>Competências</h2><div id="competence"></div></div></aside></main>`;
document.currentScript?.parentElement?.appendChild(root) || document.body.appendChild(root);

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const badge = (text, cls='') => `<span class="badge ${cls}">${esc(text)}</span>`;
function render(data) {
  const s = data.summary;
  document.querySelector('#metrics').innerHTML = [
    ['Missões',s.missions],['Ativas',s.active],['Workers',s.workers],['Artefatos',s.artifacts]
  ].map(([k,v])=>`<article><strong>${v}</strong><span>${k}</span></article>`).join('');
  document.querySelector('#missions').innerHTML = data.missions.length ? data.missions.map(m => `
    <article class="mission ${esc(m.status)}"><div class="mission-head"><div><small>${esc(m.mission_id)}</small><h3>${esc(m.objective)}</h3></div>${badge(m.status,m.status)}</div>
    <div class="workstations">${m.workers.length ? m.workers.map(w=>`<div class="worker"><span class="avatar">${esc((w.worker_id||'W').slice(-2))}</span><div><b>${esc(w.worker_id)}</b><small>${esc(w.task_id)} · ${esc(w.model||'modelo herdado')}</small></div>${badge(w.status)}</div>`).join('') : '<p class="empty">Nenhum worker ativo</p>'}</div>
    <footer>${m.tasks.map(t=>badge(`${t.task_id}: ${t.status}`)).join('')}<span>${m.artifact_count} artefatos</span></footer></article>`).join('') : '<div class="zero">Nenhuma missão registrada.</div>';
  document.querySelector('#gaps').innerHTML = data.gaps.slice(0,8).map(g=>`<div class="row"><div><b>${esc(g.title)}</b><small>${esc(g.category)}</small></div>${badge(`${g.state} · P${g.impact}`,g.state)}</div>`).join('') || '<p class="empty">Fila vazia</p>';
  document.querySelector('#fleet').innerHTML = data.fleet.hosts.map(h=>`<div class="row"><div><b>${esc(h.host_id)}</b><small>${esc(h.environment)}</small></div>${badge(h.status,h.status)}</div>`).join('') || '<p class="empty">Nenhum host registrado</p>';
  const labs = [
    ...(data.trading_lab.labs||[]).map(l=>({name:l.name, detail:`Trading · ${l.mode}`, state:l.killed?'killed':l.paused?'paused':'active'})),
    ...(data.reverse_engineering_lab.investigations||[]).map(i=>({name:i.target_type, detail:`REA · ${i.route}`, state:i.status}))
  ];
  document.querySelector('#labs').innerHTML = labs.map(l=>`<div class="row"><div><b>${esc(l.name)}</b><small>${esc(l.detail)}</small></div>${badge(l.state,l.state)}</div>`).join('') || '<p class="empty">Nenhum laboratório ativo</p>';
  document.querySelector('#competence').innerHTML = data.competencies.slice(0,8).map(c=>`<div class="row"><div><b>${esc(c.category)}</b><small>${esc(c.system?.model||'sistema')}</small></div>${badge(`${Math.round(c.best_score*100)}%`,c.state)}</div>`).join('') || '<p class="empty">Sem provas ainda</p>';
  document.querySelector('#updated').textContent = `atualizado ${new Date().toLocaleTimeString()}`;
}
async function refresh(){
  try { const r=await fetch('/api/plugins/mission-control/state'); if(!r.ok) throw new Error(`${r.status}`); render(await r.json()); root.classList.remove('offline'); }
  catch(e){ root.classList.add('offline'); document.querySelector('#updated').textContent=`indisponível: ${e.message}`; }
}
refresh(); setInterval(refresh, 3000);
