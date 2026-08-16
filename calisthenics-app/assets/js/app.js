/* ============================================================================
 * Cali100 — Logica applicativa
 *  - Router a hash (SPA), tutto client-side e offline.
 *  - Stato persistente in localStorage (con export/import).
 *  - Player di allenamento con timer, audio, wake-lock.
 *  - Gamification: XP, livello 0-100, streak, achievement.
 * ==========================================================================*/
(function (CALI) {
  'use strict';
  const { exercises, exById, skills, phases, catInfo, levels } = CALI;

  /* ------------------------------------------------------------ UTILITIES */
  const $ = (sel, root) => (root || document).querySelector(sel);
  const view = $('#view');
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function todayStr(d) { d = d || new Date(); return d.toISOString().slice(0, 10); }
  function dayOffset(str, days) { const d = new Date(str + 'T00:00:00'); d.setDate(d.getDate() + days); return todayStr(d); }
  function fmtDuration(sec) {
    const m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + String(s).padStart(2, '0');
  }

  /* ------------------------------------------------------------- STORAGE */
  const KEY = 'cali100_v1';
  function defaultState() {
    return {
      completed: {}, xp: 0, streak: { count: 0, last: null }, history: [],
      prs: {}, ach: {}, skills: {},
      settings: { sound: true, restAuto: true, keepAwake: true, restAdjust: 0, logReps: true },
      created: todayStr(),
    };
  }
  let S;
  try { S = JSON.parse(localStorage.getItem(KEY)) || defaultState(); }
  catch (e) { S = defaultState(); }
  // merge di eventuali chiavi mancanti (compatibilità futura)
  S = Object.assign(defaultState(), S);
  S.settings = Object.assign(defaultState().settings, S.settings || {});
  function save() { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} }

  /* -------------------------------------------------------- STATO DERIVATO */
  function levelCompleted(n) { return !!S.completed[n]; }
  function completedCount() { let c = 0; for (let n = 1; n <= 100; n++) if (S.completed[n]) c++; return c; }
  function nextLevel() { for (let n = 1; n <= 100; n++) if (!S.completed[n]) return n; return 101; }
  function isUnlocked(n) { return n <= nextLevel(); }
  function levelReached() { return completedCount(); }
  function liveStreak() {
    const t = todayStr();
    if (S.streak.last === t || S.streak.last === dayOffset(t, -1)) return S.streak.count;
    return 0;
  }

  /* --------------------------------------------------------- ACHIEVEMENTS */
  const ACHS = [
    { id: 'first', ico: '🎯', name: 'Primo Passo', desc: 'Completa il livello 1', test: () => levelCompleted(1) },
    { id: 'l10', ico: '🌱', name: 'Radici', desc: 'Raggiungi il livello 10', test: () => levelReached() >= 10 },
    { id: 'l25', ico: '🔨', name: 'In Costruzione', desc: 'Raggiungi il livello 25', test: () => levelReached() >= 25 },
    { id: 'l50', ico: '🔥', name: 'Metà Strada', desc: 'Raggiungi il livello 50', test: () => levelReached() >= 50 },
    { id: 'l75', ico: '💪', name: 'Bestia', desc: 'Raggiungi il livello 75', test: () => levelReached() >= 75 },
    { id: 'l100', ico: '🏆', name: 'Leggenda', desc: 'Completa il livello 100', test: () => levelReached() >= 100 },
    { id: 's3', ico: '📅', name: 'Costante', desc: '3 giorni di fila', test: () => S.streak.count >= 3 },
    { id: 's7', ico: '🗓️', name: 'Settimana Piena', desc: '7 giorni di fila', test: () => S.streak.count >= 7 },
    { id: 's30', ico: '⚡', name: 'Ferreo', desc: '30 giorni di fila', test: () => S.streak.count >= 30 },
    { id: 'w10', ico: '🔟', name: 'Dieci Sessioni', desc: '10 allenamenti totali', test: () => S.history.length >= 10 },
    { id: 'w50', ico: '🚀', name: 'Instancabile', desc: '50 allenamenti totali', test: () => S.history.length >= 50 },
    { id: 'skill', ico: '⭐', name: 'Prima Skill', desc: 'Completa una skill tree', test: () => skills.some(sk => skillDone(sk)) },
    { id: 'pr', ico: '📏', name: 'I Numeri', desc: 'Registra un record personale', test: () => Object.keys(S.prs).length > 0 },
    { id: 'earlyphase', ico: '🌿', name: 'Fondamenta Solide', desc: 'Completa la fase Fondamenta', test: () => levelReached() >= 15 },
  ];
  function skillDone(sk) {
    const st = S.skills[sk.id] || {};
    return sk.steps.every((_, i) => st[i]);
  }
  function checkAch() {
    const unlocked = [];
    ACHS.forEach((a) => {
      if (!S.ach[a.id] && a.test()) { S.ach[a.id] = todayStr(); unlocked.push(a); }
    });
    if (unlocked.length) save();
    return unlocked;
  }

  /* ------------------------------------------------------------- TOAST/UI */
  function toast(msg, gold) {
    const box = $('#toasts');
    const t = document.createElement('div');
    t.className = 'toast' + (gold ? ' gold' : '');
    t.innerHTML = msg;
    box.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; }, 2600);
    setTimeout(() => t.remove(), 3100);
  }
  function ringSVG(pct, inner, color) {
    color = color || 'var(--lime)';
    const r = 42, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(1, pct)));
    return `<div class="ring"><svg viewBox="0 0 100 100">
      <circle class="bg" cx="50" cy="50" r="${r}" fill="none" stroke-width="9"/>
      <circle class="fg" cx="50" cy="50" r="${r}" fill="none" stroke-width="9"
        stroke="${color}" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/>
    </svg><div class="ring-label">${inner}</div></div>`;
  }
  function diffDots(d) {
    let s = '<span class="diff-dots">';
    for (let i = 1; i <= 10; i++) s += `<i class="${i <= d ? 'on' : ''}"></i>`;
    return s + '</span>';
  }
  const equipLabel = { none: 'Nessun attrezzo', elevato: 'Rialzo/Sedia', sbarra: 'Sbarra', muro: 'Muro' };

  /* ============================================================ RENDER VIEWS */

  function renderHome() {
    const reached = levelReached();
    const nl = nextLevel();
    const doneAll = nl > 100;
    const lvl = doneAll ? levels[99] : levels[nl - 1];
    const ph = phases.find(p => p.id === lvl.phase);
    const strk = liveStreak();
    const totMin = S.history.reduce((a, h) => a + Math.round((h.dur || 0) / 60), 0);

    let hero;
    if (doneAll) {
      hero = `<div class="hero"><div class="hero-kicker">🏆 Percorso completato</div>
        <div class="hero-title">Hai raggiunto il Livello 100!</div>
        <p class="muted" style="margin:6px 0 14px">Continua ad allenarti: rigioca qualsiasi livello o punta alle skill.</p>
        <button class="btn btn-primary" data-action="start-level" data-n="${lvl.n}">Rigioca il Livello 100</button></div>`;
    } else {
      hero = `<div class="hero">
        <div class="hero-kicker"><span class="hero-badge">${esc(ph.emoji + ' ' + ph.name)}</span> Prossimo allenamento</div>
        <div class="hero-title">${esc(lvl.title)}</div>
        <div class="hero-meta">
          <span class="meta-pill">⏱️ <b>${lvl.est}</b> min</span>
          <span class="meta-pill">🏋️ <b>${lvl.blocks.length}</b> esercizi</span>
          <span class="meta-pill">✨ <b>${lvl.xp}</b> XP</span>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" data-action="start-level" data-n="${lvl.n}">▶ Inizia Livello ${lvl.n}</button>
        </div>
        <button class="btn btn-ghost btn-sm mt" style="width:100%" data-action="go" data-route="#/livello/${lvl.n}">Vedi la scheda</button>
      </div>`;
    }

    const ring = ringSVG(reached / 100, `<b>${reached}</b><span>/ 100</span>`);

    return `
      ${hero}
      <div class="card mt" style="display:flex; align-items:center; gap:16px;">
        ${ring}
        <div style="flex:1">
          <div class="row between"><h3 style="font-size:16px">Il tuo percorso</h3>
            <button class="btn btn-sm btn-ghost" data-action="go" data-route="#/percorso">Apri →</button></div>
          <p class="muted" style="font-size:13px; margin:4px 0 10px">Fase attuale: <b style="color:${ph.color}">${esc(ph.name)}</b></p>
          <div class="bar"><i style="width:${reached}%"></i></div>
        </div>
      </div>

      <div class="stat-grid mt">
        <div class="stat"><b style="color:var(--orange)">${strk}🔥</b><span>Streak</span></div>
        <div class="stat"><b>${S.history.length}</b><span>Sessioni</span></div>
        <div class="stat"><b style="color:var(--lime)">${S.xp}</b><span>XP</span></div>
      </div>

      <div class="section-title">Scorciatoie</div>
      <div class="btn-row">
        <button class="btn" data-action="go" data-route="#/timer">⏱️ Timer libero</button>
        <button class="btn" data-action="go" data-route="#/skill">⭐ Skill</button>
      </div>
      <button class="btn mt" style="width:100%" data-action="go" data-route="#/esercizi">📚 Libreria esercizi (${exercises.length})</button>

      <div class="callout mt-lg">💡 <b>Consiglio:</b> allenati 3-4 volte a settimana, lasciando almeno un giorno di recupero tra sessioni intense. La costanza batte l'intensità.</div>
    `;
  }

  function renderPercorso() {
    const nl = nextLevel();
    let html = `<h1 class="page-title">Percorso 0 → 100</h1>
      <p class="page-sub">${levelReached()} livelli completati · prossimo: Livello ${Math.min(nl,100)}</p>`;
    phases.forEach((p) => {
      const inPhase = levels.filter(l => l.phase === p.id);
      const doneInPhase = inPhase.filter(l => levelCompleted(l.n)).length;
      html += `<div class="phase-head">
        <span class="phase-dot" style="background:${p.color}"></span>
        <h3>${esc(p.emoji + ' ' + p.name)}</h3>
        <small>${doneInPhase}/${inPhase.length}</small></div>
        <p class="muted" style="font-size:12.5px; margin:-4px 2px 12px">${esc(p.goal)}</p>`;
      inPhase.forEach((l) => {
        const done = levelCompleted(l.n);
        const unlocked = isUnlocked(l.n);
        const current = l.n === nl;
        const cls = 'lvl' + (done ? ' done' : '') + (current ? ' current' : '') + (!unlocked ? ' locked' : '') + (l.milestone ? ' milestone' : '');
        const cta = !unlocked ? '🔒' : (done ? '↻' : '›');
        html += `<button class="${cls}" data-action="${unlocked ? 'go' : 'noop'}" data-route="#/livello/${l.n}">
          <span class="lvl-num">${done ? '✓' : l.n}</span>
          <span class="lvl-body"><b>${esc(l.focus)}</b><span>⏱ ${l.est} min · ${l.blocks.length} esercizi · ${l.xp} XP</span></span>
          ${l.milestone ? '<span class="lvl-badge">Test</span>' : ''}
          <span class="lvl-cta">${cta}</span>
        </button>`;
      });
    });
    return html;
  }

  function doseText(b) {
    if (b.unit === 'reps') return b.sets + ' × ' + b.value + (b.uni ? ' /lato' : '');
    if (b.unit === 'hold') return b.sets + ' × ' + b.value + 's';
    return b.sets + ' × ' + b.value + 's';
  }

  function renderLivello(n) {
    n = parseInt(n, 10);
    const l = levels[n - 1];
    if (!l) return renderNotFound();
    const ph = phases.find(p => p.id === l.phase);
    const done = levelCompleted(n);
    const unlocked = isUnlocked(n);

    const exBlocks = (ids, label, tag) => {
      if (!ids.length) return '';
      let h = `<div class="group-label">${label}</div>`;
      ids.forEach((it) => {
        const ex = typeof it === 'string' ? exById[it] : exById[it.ex];
        if (!ex) return;
        const ci = catInfo[ex.cat];
        const dose = typeof it === 'string'
          ? (ex.type === 'hold' ? (ex.hold ? ex.hold[0] + '-' + ex.hold[1] + 's' : '') : (ex.type === 'cardio' ? (ex.dur[0] + '-' + ex.dur[1] + 's') : ''))
          : doseText(it);
        const alt = it.ex && ex.floorAlt && exById[ex.floorAlt] ? `<div class="block-alt">↳ senza sbarra: ${esc(exById[ex.floorAlt].name)}</div>` : '';
        h += `<button class="block" data-action="go" data-route="#/esercizio/${ex.id}" style="width:100%;text-align:left">
          <div class="block-head">
            <span class="cat-badge" style="background:color-mix(in srgb, ${ci.color} 22%, var(--surface3))">${ci.emoji}</span>
            <b>${esc(ex.name)}</b>
            <span class="block-dose">${dose}</span>
          </div>
          ${it.rest ? `<div class="block-sub">Recupero ${it.rest}s · ${esc(ci.label)}</div>` : `<div class="block-sub">${esc(ci.label)}</div>`}
          ${alt}
        </button>`;
      });
      return h;
    };

    return `
      <button class="back-btn" data-action="go" data-route="#/percorso">← Percorso</button>
      <div class="hero">
        <div class="hero-kicker"><span class="hero-badge" style="background:color-mix(in srgb, ${ph.color} 20%, transparent); color:${ph.color}">${esc(ph.emoji + ' ' + ph.name)}</span> Livello ${n}${done ? ' · ✓ completato' : ''}</div>
        <div class="hero-title">${esc(l.focus)}</div>
        <div class="hero-meta">
          <span class="meta-pill">⏱️ <b>${l.est}</b> min</span>
          <span class="meta-pill">🏋️ <b>${l.blocks.length}</b> esercizi</span>
          <span class="meta-pill">✨ <b>${l.xp}</b> XP</span>
          ${l.milestone ? '<span class="meta-pill">🎯 <b>Test</b></span>' : ''}
        </div>
        ${unlocked
          ? `<button class="btn btn-primary" data-action="start-level" data-n="${n}">▶ ${done ? 'Rifai allenamento' : 'Inizia allenamento'}</button>`
          : `<button class="btn" disabled>🔒 Completa prima il livello ${n - 1}</button>`}
      </div>

      <div class="callout mt">🎯 <b>Obiettivo fase:</b> ${esc(ph.goal)}</div>

      ${exBlocks(l.warmup, '🔥 Riscaldamento (' + l.warmup.length + ')')}
      ${exBlocks(l.blocks, '💪 Allenamento (' + l.blocks.length + ')')}
      ${exBlocks(l.cooldown, '🧘 Defaticamento (' + l.cooldown.length + ')')}

      <div class="mt-lg">
        ${unlocked ? `<button class="btn btn-primary" data-action="start-level" data-n="${n}">▶ ${done ? 'Rifai' : 'Inizia'} il Livello ${n}</button>` : ''}
      </div>
    `;
  }

  let exFilter = 'all';
  function renderEsercizi() {
    const cats = [['all', 'Tutti', '📋']].concat(
      Object.keys(catInfo).map(k => [k, catInfo[k].label, catInfo[k].emoji]));
    let chips = '<div class="filters">';
    cats.forEach(([k, lbl, emo]) => {
      chips += `<button class="fchip ${exFilter === k ? 'active' : ''}" data-action="filter-ex" data-cat="${k}">${emo} ${esc(lbl)}</button>`;
    });
    chips += '</div>';

    const list = exercises
      .filter(e => exFilter === 'all' || e.cat === exFilter)
      .sort((a, b) => a.diff - b.diff);

    let items = '';
    list.forEach((ex) => {
      const ci = catInfo[ex.cat];
      items += `<button class="ex-item" data-action="go" data-route="#/esercizio/${ex.id}">
        <span class="ex-thumb" style="background:color-mix(in srgb, ${ci.color} 22%, var(--surface3))">${ci.emoji}</span>
        <span style="flex:1;min-width:0">
          <b>${esc(ex.name)}</b>
          <span class="ex-meta">${esc(ci.label)} ${diffDots(ex.diff)}</span>
        </span>
        <span class="lvl-cta">›</span>
      </button>`;
    });

    return `<h1 class="page-title">Esercizi</h1>
      <p class="page-sub">${exercises.length} esercizi a corpo libero, per gruppo e difficoltà</p>
      ${chips}
      ${items || '<div class="empty">Nessun esercizio in questa categoria.</div>'}`;
  }

  function renderEsercizio(id) {
    const ex = exById[id];
    if (!ex) return renderNotFound();
    const ci = catInfo[ex.cat];
    const typeLabel = ex.type === 'reps' ? 'Ripetizioni' : ex.type === 'hold' ? 'Isometrico (tenuta)' : 'A tempo';
    const doseLabel = ex.type === 'reps' ? (ex.rep ? ex.rep[0] + '-' + ex.rep[1] + ' rip' + (ex.uni ? '/lato' : '') : '')
      : ex.type === 'hold' ? (ex.hold ? ex.hold[0] + '-' + ex.hold[1] + ' sec' : '')
      : (ex.dur ? ex.dur[0] + '-' + ex.dur[1] + ' sec' : '');
    const reg = ex.reg && exById[ex.reg], prog = ex.prog && exById[ex.prog], floor = ex.floorAlt && exById[ex.floorAlt];

    return `
      <button class="back-btn" data-action="back">← Indietro</button>
      <div class="ex-hero">
        <div class="big-emoji">${ci.emoji}</div>
        <h1>${esc(ex.name)}</h1>
        <div class="tags">
          <span class="tag" style="color:${ci.color}">${esc(ci.label)}</span>
          <span class="tag">${esc(typeLabel)}</span>
          <span class="tag">${esc(equipLabel[ex.equip] || ex.equip)}</span>
          ${doseLabel ? `<span class="tag">${esc(doseLabel)}</span>` : ''}
        </div>
        <div class="mt" style="display:flex;align-items:center;justify-content:center;gap:8px">
          <span class="muted" style="font-size:12px">Difficoltà</span>${diffDots(ex.diff)}<span class="muted" style="font-size:12px">${ex.diff}/10</span>
        </div>
      </div>

      <p style="font-size:14.5px; margin:0 2px 14px">${esc(ex.desc)}</p>

      <div class="section-title">Muscoli coinvolti</div>
      <div class="tags" style="margin:0 2px">${ex.muscles.map(m => `<span class="tag">${esc(m)}</span>`).join('')}</div>

      ${ex.cues && ex.cues.length ? `<div class="section-title">Tecnica corretta</div>
        <div class="card"><ul class="list-check">${ex.cues.map(c => `<li>${esc(c)}</li>`).join('')}</ul></div>` : ''}

      ${ex.errori && ex.errori.length ? `<div class="section-title">Errori da evitare</div>
        <div class="card"><ul class="list-x">${ex.errori.map(c => `<li>${esc(c)}</li>`).join('')}</ul></div>` : ''}

      ${floor ? `<div class="callout mt-lg">🔁 <b>Senza sbarra:</b> in alternativa puoi fare <a data-action="go" data-route="#/esercizio/${floor.id}">${esc(floor.name)}</a>.</div>` : ''}

      ${(reg || prog) ? `<div class="section-title">Progressione</div>
        <div class="prog-links">
          ${reg ? `<button class="btn" data-action="go" data-route="#/esercizio/${reg.id}">⬇ Più facile<br><small class="muted">${esc(reg.name)}</small></button>` : ''}
          ${prog ? `<button class="btn" data-action="go" data-route="#/esercizio/${prog.id}">⬆ Più difficile<br><small class="muted">${esc(prog.name)}</small></button>` : ''}
        </div>` : ''}
    `;
  }

  function renderSkillList() {
    let html = `<h1 class="page-title">Skill Tree</h1>
      <p class="page-sub">Percorsi guidati verso le skill iconiche del calisthenics</p>`;
    skills.forEach((sk) => {
      const st = S.skills[sk.id] || {};
      const done = sk.steps.filter((_, i) => st[i]).length;
      const pct = Math.round(done / sk.steps.length * 100);
      html += `<button class="skill-card" data-action="go" data-route="#/skill/${sk.id}"
        style="background:linear-gradient(135deg, color-mix(in srgb, ${sk.color} 16%, var(--surface)), var(--surface2))">
        <div class="row between"><span class="emoji">${sk.emoji}</span>
          ${skillDone(sk) ? '<span class="lvl-badge" style="background:color-mix(in srgb,'+sk.color+' 22%,transparent);color:'+sk.color+'">Completata</span>' : ''}
        </div>
        <h3>${esc(sk.name)}</h3>
        <p>${esc(sk.desc)}</p>
        <div class="mini-bar bar"><i style="width:${pct}%; background:${sk.color}"></i></div>
        <p class="muted" style="font-size:12px;margin-top:6px">${done}/${sk.steps.length} tappe</p>
      </button>`;
    });
    return html;
  }

  function renderSkill(id) {
    const sk = skills.find(s => s.id === id);
    if (!sk) return renderNotFound();
    const st = S.skills[sk.id] || {};
    let steps = '<div class="skill-steps">';
    sk.steps.forEach((step, i) => {
      const ex = exById[step.ex];
      const isDone = !!st[i];
      steps += `<div class="step ${isDone ? 'done' : ''}">
        <div class="step-dot">${isDone ? '✓' : (i + 1)}</div>
        <div class="step-body">
          <b>${esc(ex ? ex.name : step.ex)}</b>
          <span>🎯 ${esc(step.goal)}</span>
          ${ex ? `<div style="margin-top:6px"><a class="tag" data-action="go" data-route="#/esercizio/${ex.id}">Vedi esercizio →</a></div>` : ''}
        </div>
        <button class="step-check" data-action="toggle-skill" data-skill="${sk.id}" data-idx="${i}">${isDone ? 'Fatto' : 'Segna'}</button>
      </div>`;
    });
    steps += '</div>';

    const done = sk.steps.filter((_, i) => st[i]).length;
    const pct = Math.round(done / sk.steps.length * 100);
    return `
      <button class="back-btn" data-action="go" data-route="#/skill">← Skill</button>
      <div class="ex-hero" style="background:linear-gradient(135deg, color-mix(in srgb, ${sk.color} 20%, var(--surface)), var(--surface))">
        <div class="big-emoji">${sk.emoji}</div>
        <h1>${esc(sk.name)}</h1>
        <p class="muted" style="margin-top:6px;font-size:13.5px">${esc(sk.desc)}</p>
        <div class="bar mt" style="max-width:280px;margin:14px auto 0"><i style="width:${pct}%;background:${sk.color}"></i></div>
        <p class="muted" style="font-size:12px;margin-top:6px">${done}/${sk.steps.length} tappe completate</p>
      </div>
      <div class="callout mt">Segna una tappa quando raggiungi l'obiettivo indicato. Allena la tappa attuale 2-3 volte a settimana con recuperi lunghi.</div>
      ${steps}
    `;
  }

  function renderProgressi() {
    const reached = levelReached();
    const totMin = S.history.reduce((a, h) => a + Math.round((h.dur || 0) / 60), 0);
    const strk = liveStreak();

    // calendario ultimi 28 giorni
    const daysDone = {};
    S.history.forEach(h => { daysDone[h.date] = (daysDone[h.date] || 0) + 1; });
    let cal = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px">';
    for (let i = 27; i >= 0; i--) {
      const d = dayOffset(todayStr(), -i);
      const on = daysDone[d];
      cal += `<div title="${d}" style="aspect-ratio:1;border-radius:7px;background:${on ? 'var(--lime)' : 'var(--surface3)'};opacity:${on ? 1 : .5}"></div>`;
    }
    cal += '</div>';

    // record personali
    const prsDef = [
      ['pushup', 'Piegamenti (max rip)'], ['pullup', 'Trazioni (max rip)'],
      ['squat', 'Squat (max rip)'], ['dip', 'Dip (max rip)'],
      ['plank', 'Plank (sec)'], ['lsit', 'L-sit (sec)'], ['handstand', 'Verticale (sec)'],
    ];
    let prRows = '';
    prsDef.forEach(([k, lbl]) => {
      prRows += `<div class="pr-row"><label>${esc(lbl)}</label>
        <input type="number" inputmode="numeric" min="0" data-pr="${k}" value="${S.prs[k] != null ? S.prs[k] : ''}" placeholder="—"></div>`;
    });

    // achievement
    let achHtml = '<div class="ach-grid">';
    ACHS.forEach((a) => {
      const on = !!S.ach[a.id];
      achHtml += `<div class="ach ${on ? 'on' : ''}"><div class="ico">${a.ico}</div><b>${esc(a.name)}</b><span>${esc(a.desc)}</span></div>`;
    });
    achHtml += '</div>';

    // storico recente
    let hist = '';
    const recent = S.history.slice(-8).reverse();
    if (recent.length) {
      hist = recent.map(h => `<div class="row between" style="padding:9px 0;border-bottom:1px solid var(--line)">
        <span><b>Livello ${h.levelN}</b> <span class="muted" style="font-size:12px">${esc(h.date)}</span></span>
        <span class="muted" style="font-size:13px">⏱ ${fmtDuration(h.dur || 0)} · +${h.xp} XP</span></div>`).join('');
    } else {
      hist = '<div class="empty"><div class="big">🏁</div>Nessun allenamento ancora. Inizia dal Livello 1!</div>';
    }

    return `<h1 class="page-title">Progressi</h1>
      <div class="stat-grid">
        <div class="stat"><b>${reached}</b><span>Livello</span></div>
        <div class="stat"><b style="color:var(--orange)">${strk}</b><span>Streak</span></div>
        <div class="stat"><b style="color:var(--lime)">${S.xp}</b><span>XP</span></div>
      </div>
      <div class="stat-grid mt">
        <div class="stat"><b>${S.history.length}</b><span>Sessioni</span></div>
        <div class="stat"><b>${totMin}</b><span>Minuti</span></div>
        <div class="stat"><b>${Object.values(S.ach).length}/${ACHS.length}</b><span>Trofei</span></div>
      </div>

      <div class="section-title">Ultimi 28 giorni</div>
      <div class="card">${cal}</div>

      <div class="section-title">Record personali</div>
      <div class="card">${prRows}
        <button class="btn btn-primary btn-sm mt" data-action="save-prs" style="width:100%">Salva record</button>
      </div>

      <div class="section-title">Trofei</div>
      ${achHtml}

      <div class="section-title">Storico allenamenti</div>
      <div class="card">${hist}</div>
    `;
  }

  function renderImpostazioni() {
    const s = S.settings;
    const sw = (key, label, sub) => `<div class="switch-row">
      <div><b style="font-size:14.5px">${esc(label)}</b>${sub ? `<div class="muted" style="font-size:12.5px">${esc(sub)}</div>` : ''}</div>
      <label class="switch"><input type="checkbox" data-setting="${key}" ${s[key] ? 'checked' : ''}><span class="track"></span><span class="thumb"></span></label>
    </div>`;

    return `<h1 class="page-title">Impostazioni</h1>
      <div class="card">
        ${sw('sound', 'Suoni del timer', 'Bip di conto alla rovescia e fine recupero')}
        ${sw('keepAwake', 'Schermo sempre acceso', 'Durante l\'allenamento (se supportato)')}
        ${sw('restAuto', 'Recupero automatico', 'Avvia il conto alla rovescia dopo ogni serie')}
        ${sw('logReps', 'Registra ripetizioni', 'Chiedi le ripetizioni svolte durante la sessione')}
      </div>

      <div class="section-title">Recupero personalizzato</div>
      <div class="card">
        <div class="row between"><b style="font-size:14.5px">Aggiusta recuperi</b>
          <span id="restAdjLbl" style="color:var(--lime);font-weight:800">${s.restAdjust > 0 ? '+' : ''}${s.restAdjust}s</span></div>
        <input type="range" min="-30" max="30" step="5" value="${s.restAdjust}" data-setting-range="restAdjust" style="width:100%;margin-top:12px">
        <p class="muted" style="font-size:12px;margin-top:6px">Applica un aumento o una riduzione a tutti i tempi di recupero.</p>
      </div>

      <div class="section-title">I tuoi dati</div>
      <div class="card">
        <p class="muted" style="font-size:13px;margin-bottom:12px">Tutto è salvato solo su questo dispositivo. Esporta un backup o trasferiscilo su un altro telefono.</p>
        <div class="btn-row">
          <button class="btn btn-sm" data-action="export">⬇ Esporta backup</button>
          <button class="btn btn-sm" data-action="import">⬆ Importa</button>
        </div>
        <textarea id="ioBox" placeholder="Il backup (JSON) apparirà qui. Per importare, incolla qui un backup e premi Importa." style="width:100%;height:110px;margin-top:12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;color:var(--text);font-size:12px;font-family:monospace"></textarea>
      </div>

      <div class="section-title">Zona pericolosa</div>
      <div class="card">
        <button class="btn btn-danger" data-action="reset">🗑️ Azzera tutti i progressi</button>
      </div>

      <p class="muted center mt-lg" style="font-size:12px">Cali100 · PWA offline · v1.0<br>Made for personal training 💪</p>
    `;
  }

  function renderNotFound() {
    return `<div class="empty"><div class="big">🤷</div>Pagina non trovata.<br>
      <button class="btn btn-sm mt" data-action="go" data-route="#/">Torna alla Home</button></div>`;
  }

  /* =============================================================== TIMER LIBERO */
  function renderTimer() {
    return `<h1 class="page-title">Timer libero</h1>
      <p class="page-sub">Circuito a intervalli (HIIT / Tabata). Personalizza e avvia.</p>
      <div class="card">
        <div class="field"><label>Lavoro (secondi)</label><input type="number" id="tWork" value="30" inputmode="numeric"></div>
        <div class="field"><label>Recupero (secondi)</label><input type="number" id="tRest" value="15" inputmode="numeric"></div>
        <div class="field"><label>Round (giri)</label><input type="number" id="tRounds" value="8" inputmode="numeric"></div>
        <div class="field"><label>Esercizi per round (opzionale, uno per riga)</label>
          <textarea id="tEx" rows="3" placeholder="Es:\nBurpee\nMountain climber\nPlank" style="width:100%;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;color:var(--text)"></textarea></div>
        <button class="btn btn-primary" data-action="start-timer">▶ Avvia circuito</button>
      </div>
      <div class="callout mt">🔥 <b>Tabata classico:</b> 20s lavoro / 10s recupero × 8 round. Prova anche 40/20 per un condizionamento più intenso.</div>`;
  }

  /* ================================================================ ROUTER */
  const routes = [
    [/^#\/$/, () => renderHome()],
    [/^#\/percorso$/, () => renderPercorso()],
    [/^#\/livello\/(\d+)$/, (m) => renderLivello(m[1])],
    [/^#\/esercizi$/, () => renderEsercizi()],
    [/^#\/esercizio\/([\w-]+)$/, (m) => renderEsercizio(m[1])],
    [/^#\/skill$/, () => renderSkillList()],
    [/^#\/skill\/([\w-]+)$/, (m) => renderSkill(m[1])],
    [/^#\/progressi$/, () => renderProgressi()],
    [/^#\/timer$/, () => renderTimer()],
    [/^#\/impostazioni$/, () => renderImpostazioni()],
  ];
  function router() {
    const hash = location.hash || '#/';
    let out = null;
    for (const [re, fn] of routes) { const m = hash.match(re); if (m) { out = fn(m); break; } }
    view.innerHTML = out != null ? out : renderNotFound();
    view.scrollTop = 0; window.scrollTo(0, 0);
    // aggiorna nav attiva
    const base = '#/' + (hash.split('/')[1] || '');
    document.querySelectorAll('.nav-btn').forEach(b => {
      const r = b.getAttribute('data-route');
      b.classList.toggle('active', r === hash || (r !== '#/' && hash.indexOf(r) === 0) || (r === base));
    });
    updateHeader();
  }
  function updateHeader() {
    $('#hdrLevel').textContent = 'Lv ' + levelReached();
    $('#hdrStreak').textContent = liveStreak();
  }
  function go(route) { if (location.hash === route) router(); else location.hash = route; }

  /* ========================================================= AUDIO / WAKE */
  let audioCtx = null;
  function beep(freq, dur, vol) {
    if (!S.settings.sound) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.frequency.value = freq; o.type = 'sine';
      g.gain.value = vol || 0.15;
      o.connect(g); g.connect(audioCtx.destination);
      o.start();
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + (dur || 0.15));
      o.stop(audioCtx.currentTime + (dur || 0.15));
    } catch (e) {}
  }
  let wakeLock = null;
  async function acquireWake() {
    if (!S.settings.keepAwake) return;
    try { if ('wakeLock' in navigator) wakeLock = await navigator.wakeLock.request('screen'); } catch (e) {}
  }
  function releaseWake() { try { if (wakeLock) { wakeLock.release(); wakeLock = null; } } catch (e) {} }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && PL.active) acquireWake();
  });

  /* ================================================================ PLAYER */
  const player = $('#player');
  const PL = { active: false, steps: [], i: 0, phase: 'work', timed: false, running: false,
    workLeft: 0, restLeft: 0, tick: null, startTs: 0, logged: {}, curReps: 0, level: null, isTimer: false };

  function clearTick() { if (PL.tick) { clearInterval(PL.tick); PL.tick = null; } }

  // Costruisce la sequenza di step da un livello.
  function buildSteps(level) {
    const steps = [];
    const push = (id, section, opts) => {
      const ex = exById[id];
      if (!ex) return;
      const sets = opts.sets || 1;
      for (let s = 1; s <= sets; s++) {
        let unit, target;
        if (section === 'work') { unit = opts.unit; target = opts.value; }
        else { // warmup/cooldown: usa metà range
          if (ex.type === 'reps') { unit = 'reps'; target = ex.rep ? Math.round((ex.rep[0] + ex.rep[1]) / 2) : 10; }
          else if (ex.type === 'hold') { unit = 'hold'; target = ex.hold ? ex.hold[0] : 20; }
          else { unit = 'cardio'; target = ex.dur ? ex.dur[0] : 30; }
        }
        steps.push({
          exId: id, section, unit, target,
          setIdx: s, setTot: sets, uni: !!ex.uni,
          rest: section === 'work' ? opts.rest : 0,
          role: opts.role,
        });
      }
    };
    level.warmup.forEach(id => push(id, 'warmup', {}));
    level.blocks.forEach(b => push(b.ex, 'work', { sets: b.sets, unit: b.unit, value: b.value, rest: b.rest, role: b.role }));
    level.cooldown.forEach(id => push(id, 'cooldown', {}));
    return steps;
  }

  function startLevel(n) {
    n = parseInt(n, 10);
    const level = levels[n - 1];
    if (!level || !isUnlocked(n)) { toast('🔒 Livello ancora bloccato'); return; }
    PL.active = true; PL.isTimer = false; PL.level = level;
    PL.steps = buildSteps(level); PL.i = 0; PL.logged = {}; PL.startTs = Date.now();
    player.hidden = false; document.body.style.overflow = 'hidden';
    acquireWake();
    // sblocca l'audio con il gesto utente
    try { audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)(); if (audioCtx.state === 'suspended') audioCtx.resume(); } catch (e) {}
    showStep(0);
  }

  function closePlayer() {
    clearTick(); releaseWake();
    PL.active = false; player.hidden = true; document.body.style.overflow = '';
    router();
  }

  const SECTION_LABEL = { warmup: '🔥 Riscaldamento', work: '💪 Allenamento', cooldown: '🧘 Defaticamento' };

  function showStep(i) {
    clearTick();
    PL.i = i; PL.phase = 'work';
    const step = PL.steps[i];
    const ex = exById[step.exId];
    const ci = catInfo[ex.cat];
    PL.timed = step.unit !== 'reps';

    const total = PL.steps.length;
    const isWork = step.section === 'work';
    const setInfo = isWork ? (step.setTot > 1 ? `Serie ${step.setIdx} di ${step.setTot}` : 'Serie unica') : '';
    const catBadge = isWork
      ? `<div class="pl-cat" style="background:color-mix(in srgb, ${ci.color} 20%, transparent); color:${ci.color}">${ci.emoji} ${esc(ci.label)}</div>`
      : '';
    const cues = (ex.cues || []).slice(0, 2);

    let body;
    if (PL.timed) {
      body = `<div class="pl-timer-wrap" data-action="pl-pause">
        ${timerRing(step.target, step.target, 'var(--lime)')}
        <div class="pl-timer-num" id="plNum">${step.target}</div>
      </div>
      <div class="pl-hint" id="plHint">${step.unit === 'hold' ? 'Mantieni la posizione' : 'Lavora al ritmo indicato'} · tocca per pausa</div>`;
    } else {
      PL.curReps = step.target;
      body = `<div class="pl-log">
        <button data-action="pl-rep" data-d="-1">−</button>
        <div><b id="plReps">${step.target}</b><span>ripetizioni${step.uni ? ' /lato' : ''}</span></div>
        <button data-action="pl-rep" data-d="1">+</button>
      </div>`;
    }

    const bottom = PL.timed
      ? `<button class="btn btn-primary" data-action="pl-done-timed">Fatto ✓</button>`
      : `<button class="btn btn-primary" data-action="pl-done-reps">Completa serie ✓</button>`;

    player.innerHTML = `
      <div class="pl-top">
        <button class="pl-close" data-action="pl-close">✕</button>
        <div class="pl-progress"><div class="bar"><i id="plBar" style="width:${(i / total * 100).toFixed(1)}%"></i></div></div>
        <div class="pl-step-count">${i + 1}/${total}</div>
      </div>
      <div class="pl-main">
        ${catBadge}
        <div class="pl-kicker">${SECTION_LABEL[step.section]}</div>
        <div class="pl-name">${esc(ex.name)}</div>
        ${setInfo ? `<div class="pl-set">${esc(setInfo)}</div>` : ''}
        ${body}
        <ul class="pl-cues">${cues.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
        <button class="btn btn-ghost btn-sm mt" data-action="go-ex" data-id="${ex.id}">Come si esegue →</button>
      </div>
      <div class="pl-bottom">${bottom}</div>`;

    if (PL.timed) { PL.workLeft = step.target; PL.running = true; PL.tick = setInterval(onTick, 1000); }
  }

  function timerRing(left, total, color) {
    const r = 46, c = 2 * Math.PI * r, off = c * (1 - left / total);
    return `<svg viewBox="0 0 100 100">
      <circle class="bg" cx="50" cy="50" r="${r}" fill="none" stroke-width="7"/>
      <circle class="fg" id="plRing" cx="50" cy="50" r="${r}" fill="none" stroke-width="7" stroke="${color}"
        stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/></svg>`;
  }
  function setRing(left, total) {
    const el = $('#plRing'); if (!el) return;
    const r = 46, c = 2 * Math.PI * r;
    el.setAttribute('stroke-dashoffset', (c * (1 - left / total)).toFixed(1));
  }

  function onTick() {
    if (PL.phase === 'rest') {
      PL.restLeft--;
      const num = $('#plNum'); if (num) num.textContent = PL.restLeft;
      setRing(PL.restLeft, PL.restTotal);
      if (PL.restLeft <= 3 && PL.restLeft > 0) beep(880, 0.08, 0.1);
      if (PL.restLeft <= 0) { clearTick(); beep(1320, 0.18, 0.14); advance(); }
    } else if (PL.timed && PL.running) {
      PL.workLeft--;
      const num = $('#plNum'); if (num) num.textContent = PL.workLeft;
      setRing(PL.workLeft, PL.steps[PL.i].target);
      if (PL.workLeft <= 3 && PL.workLeft > 0) beep(880, 0.08, 0.1);
      if (PL.workLeft <= 0) { clearTick(); beep(1320, 0.18, 0.14); PL.isTimer ? advanceFree() : afterWork(); }
    }
  }

  function afterWork() {
    const step = PL.steps[PL.i];
    const isLast = PL.i >= PL.steps.length - 1;
    if (!isLast && step.rest > 0 && S.settings.restAuto) startRest(step.rest);
    else advance();
  }

  function completeReps() {
    const step = PL.steps[PL.i];
    const ex = exById[step.exId];
    if (S.settings.logReps) {
      PL.logged[ex.id] = Math.max(PL.logged[ex.id] || 0, PL.curReps || step.target);
    }
    afterWork();
  }

  function startRest(sec) {
    let dur = sec + (S.settings.restAdjust || 0);
    dur = Math.max(5, dur);
    PL.phase = 'rest'; PL.restLeft = dur; PL.restTotal = dur;
    const nextStep = PL.steps[PL.i + 1];
    const nextEx = nextStep ? exById[nextStep.exId] : null;
    const nextInfo = nextStep
      ? `${esc(nextEx.name)} · ${nextStep.unit === 'reps' ? (nextStep.target + ' rip' + (nextStep.uni ? '/lato' : '')) : nextStep.target + 's'}`
      : 'Fine allenamento';
    player.innerHTML = `
      <div class="pl-top">
        <button class="pl-close" data-action="pl-close">✕</button>
        <div class="pl-progress"><div class="bar"><i style="width:${((PL.i + 1) / PL.steps.length * 100).toFixed(1)}%"></i></div></div>
        <div class="pl-step-count">${PL.i + 1}/${PL.steps.length}</div>
      </div>
      <div class="pl-main pl-rest">
        <div class="pl-kicker">Recupero</div>
        <div class="pl-timer-wrap">
          ${timerRing(dur, dur, 'var(--cyan)')}
          <div class="pl-timer-num" id="plNum">${dur}</div>
        </div>
        <div class="pl-hint">Prossimo: <b style="color:var(--text)">${nextInfo}</b></div>
      </div>
      <div class="pl-bottom">
        <div class="btn-row">
          <button class="btn" data-action="pl-rest-adj" data-d="-15">−15s</button>
          <button class="btn" data-action="pl-rest-adj" data-d="15">+15s</button>
        </div>
        <button class="btn btn-primary" data-action="pl-skip-rest">Salta recupero →</button>
      </div>`;
    PL.tick = setInterval(onTick, 1000);
  }

  function advance() {
    clearTick();
    if (PL.i >= PL.steps.length - 1) { finish(); return; }
    showStep(PL.i + 1);
  }

  function finish() {
    clearTick(); releaseWake();
    const durSec = Math.round((Date.now() - PL.startTs) / 1000);

    if (PL.isTimer) { // circuito libero: nessun salvataggio percorso
      player.innerHTML = doneScreen('Circuito completato!', 0, [], durSec, false);
      return;
    }

    const level = PL.level;
    const already = levelCompleted(level.n);
    const leveledUp = !already;
    // Salvataggio progressi
    if (!already) S.completed[level.n] = { date: todayStr(), xp: level.xp };
    S.xp += level.xp;
    S.history.push({ date: todayStr(), levelN: level.n, dur: durSec, xp: level.xp });
    // streak
    const t = todayStr();
    if (S.streak.last === t) { /* già contato oggi */ }
    else if (S.streak.last === dayOffset(t, -1)) { S.streak.count++; S.streak.last = t; }
    else { S.streak.count = 1; S.streak.last = t; }
    // PR automatici
    const PR_MAP = { pushup: 'pushup', wide_pushup: 'pushup', diamond_pushup: 'pushup',
      pullup: 'pullup', chinup: 'pullup', wide_pullup: 'pullup',
      squat: 'squat', bench_dip: 'dip', parallel_dip: 'dip', plank: 'plank', lsit: 'lsit',
      freestanding_handstand: 'handstand', wall_handstand_hold: 'handstand' };
    Object.keys(PL.logged).forEach(exid => {
      const k = PR_MAP[exid]; if (!k) return;
      const v = PL.logged[exid];
      if (v > (S.prs[k] || 0)) S.prs[k] = v;
    });
    save();
    const newAch = checkAch();

    player.innerHTML = doneScreen(
      leveledUp ? 'Livello ' + level.n + ' completato!' : 'Allenamento completato!',
      level.xp, newAch, durSec, leveledUp);
    // celebra
    beep(880, 0.12, 0.12); setTimeout(() => beep(1174, 0.12, 0.12), 130); setTimeout(() => beep(1568, 0.2, 0.14), 260);
    if (newAch.length) newAch.forEach((a, idx) => setTimeout(() => toast(`${a.ico} Trofeo sbloccato: <b>${esc(a.name)}</b>`, true), 400 + idx * 400));
  }

  function doneScreen(title, xp, newAch, durSec, leveledUp) {
    const reached = levelReached();
    return `<div class="pl-done">
      <div class="trophy">${leveledUp ? '🏆' : '✅'}</div>
      <h1>${esc(title)}</h1>
      ${xp ? `<div class="xp-gain">+${xp} XP</div>` : ''}
      <div class="summ">
        <div><b>${fmtDuration(durSec)}</b><span>Durata</span></div>
        ${!PL.isTimer ? `<div><b>${reached}</b><span>Livello</span></div>` : ''}
        <div><b>${liveStreak()}🔥</b><span>Streak</span></div>
      </div>
      ${newAch && newAch.length ? `<div class="mt" style="margin-bottom:14px">${newAch.map(a => `<span class="tag" style="color:var(--yellow);margin:3px">${a.ico} ${esc(a.name)}</span>`).join('')}</div>` : ''}
      <div style="width:100%;max-width:340px">
        <button class="btn btn-primary" data-action="pl-finish-nav">${leveledUp && reached < 100 ? 'Vai al prossimo livello →' : 'Torna al percorso'}</button>
        <button class="btn btn-ghost mt" data-action="pl-close">Chiudi</button>
      </div>
    </div>`;
  }

  /* ---- Timer libero (circuito) ---- */
  function startFreeTimer(work, rest, rounds, exNames) {
    PL.active = true; PL.isTimer = true; PL.level = null; PL.i = 0; PL.startTs = Date.now();
    const steps = [];
    const names = exNames && exNames.length ? exNames : ['Lavoro'];
    for (let r = 1; r <= rounds; r++) {
      names.forEach((nm) => {
        steps.push({ freeName: nm, freeRound: r, freeRounds: rounds, section: 'work', unit: 'cardio', target: work, setTot: 1, setIdx: 1, rest: rest, uni: false });
      });
    }
    PL.steps = steps;
    player.hidden = false; document.body.style.overflow = 'hidden';
    acquireWake();
    try { audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)(); if (audioCtx.state === 'suspended') audioCtx.resume(); } catch (e) {}
    showFreeStep(0);
  }
  function showFreeStep(i) {
    clearTick(); PL.i = i; PL.phase = 'work'; PL.timed = true;
    const step = PL.steps[i];
    PL.workLeft = step.target;
    player.innerHTML = `
      <div class="pl-top">
        <button class="pl-close" data-action="pl-close">✕</button>
        <div class="pl-progress"><div class="bar"><i style="width:${(i / PL.steps.length * 100).toFixed(1)}%"></i></div></div>
        <div class="pl-step-count">${i + 1}/${PL.steps.length}</div>
      </div>
      <div class="pl-main">
        <div class="pl-cat" style="background:color-mix(in srgb, var(--orange) 20%, transparent); color:var(--orange)">⏱️ Round ${step.freeRound}/${step.freeRounds}</div>
        <div class="pl-name">${esc(step.freeName)}</div>
        <div class="pl-timer-wrap" data-action="pl-pause">
          ${timerRing(step.target, step.target, 'var(--lime)')}
          <div class="pl-timer-num" id="plNum">${step.target}</div>
        </div>
        <div class="pl-hint">tocca per pausa</div>
      </div>
      <div class="pl-bottom"><button class="btn btn-primary" data-action="pl-done-timed">Salta →</button></div>`;
    PL.running = true; PL.tick = setInterval(onTick, 1000);
  }

  /* ============================================================ EVENT DISPATCH */
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-action]');
    if (!t) return;
    const a = t.getAttribute('data-action');
    switch (a) {
      case 'go': go(t.getAttribute('data-route')); break;
      case 'back': history.length > 1 ? history.back() : go('#/'); break;
      case 'noop': toast('🔒 Completa prima i livelli precedenti'); break;
      case 'start-level': startLevel(t.getAttribute('data-n')); break;
      case 'filter-ex': exFilter = t.getAttribute('data-cat'); router(); break;
      case 'toggle-skill': toggleSkill(t.getAttribute('data-skill'), +t.getAttribute('data-idx')); break;
      case 'save-prs': savePRs(); break;
      case 'export': doExport(); break;
      case 'import': doImport(); break;
      case 'reset': doReset(); break;
      case 'start-timer': {
        const w = Math.max(5, +$('#tWork').value || 30), r = Math.max(0, +$('#tRest').value || 15),
          n = Math.max(1, Math.min(50, +$('#tRounds').value || 8));
        const ex = ($('#tEx').value || '').split('\n').map(s => s.trim()).filter(Boolean);
        startFreeTimer(w, r, n, ex); break;
      }
      // ---- player ----
      case 'pl-close': closePlayer(); break;
      case 'pl-pause': togglePause(); break;
      case 'pl-rep': adjReps(+t.getAttribute('data-d')); break;
      case 'pl-done-reps': completeReps(); break;
      case 'pl-done-timed': clearTick(); PL.isTimer ? advanceFree() : afterWork(); break;
      case 'pl-rest-adj': adjRest(+t.getAttribute('data-d')); break;
      case 'pl-skip-rest': clearTick(); PL.isTimer ? advanceFree() : advance(); break;
      case 'pl-finish-nav': finishNav(); break;
      case 'go-ex': closePlayer(); go('#/esercizio/' + t.getAttribute('data-id')); break;
    }
  });
  // gestione input (settings, range, prs)
  document.addEventListener('change', (e) => {
    const s = e.target;
    if (s.hasAttribute('data-setting')) {
      S.settings[s.getAttribute('data-setting')] = s.checked; save();
      toast('Impostazione salvata');
    }
  });
  document.addEventListener('input', (e) => {
    const s = e.target;
    if (s.hasAttribute('data-setting-range')) {
      S.settings[s.getAttribute('data-setting-range')] = +s.value;
      const lbl = $('#restAdjLbl'); if (lbl) lbl.textContent = (s.value > 0 ? '+' : '') + s.value + 's';
      save();
    }
  });

  function togglePause() {
    if (PL.phase !== 'work' || !PL.timed) return;
    PL.running = !PL.running;
    const hint = $('#plHint'); if (hint) hint.textContent = PL.running ? 'tocca per pausa' : '⏸ In pausa — tocca per riprendere';
  }
  function adjReps(d) {
    PL.curReps = Math.max(0, (PL.curReps || 0) + d);
    const el = $('#plReps'); if (el) el.textContent = PL.curReps;
  }
  function adjRest(d) {
    PL.restLeft = Math.max(1, PL.restLeft + d); PL.restTotal = Math.max(PL.restTotal, PL.restLeft);
    const num = $('#plNum'); if (num) num.textContent = PL.restLeft;
    setRing(PL.restLeft, PL.restTotal);
  }
  function advanceFree() {
    clearTick();
    const step = PL.steps[PL.i];
    const isLast = PL.i >= PL.steps.length - 1;
    if (!isLast && step.rest > 0) { startRestFree(step.rest); }
    else if (isLast) { finish(); }
    else showFreeStep(PL.i + 1);
  }
  function startRestFree(sec) {
    PL.phase = 'rest'; PL.restLeft = sec; PL.restTotal = sec;
    const nextStep = PL.steps[PL.i + 1];
    player.innerHTML = `
      <div class="pl-top">
        <button class="pl-close" data-action="pl-close">✕</button>
        <div class="pl-progress"><div class="bar"><i style="width:${((PL.i + 1) / PL.steps.length * 100).toFixed(1)}%"></i></div></div>
        <div class="pl-step-count">${PL.i + 1}/${PL.steps.length}</div>
      </div>
      <div class="pl-main pl-rest">
        <div class="pl-kicker">Recupero</div>
        <div class="pl-timer-wrap">${timerRing(sec, sec, 'var(--cyan)')}<div class="pl-timer-num" id="plNum">${sec}</div></div>
        <div class="pl-hint">Prossimo: <b style="color:var(--text)">${nextStep ? esc(nextStep.freeName) : 'Fine'}</b></div>
      </div>
      <div class="pl-bottom"><button class="btn btn-primary" data-action="pl-skip-rest">Salta recupero →</button></div>`;
    // override advance target: when rest ends in free mode
    PL._freeRest = true;
    PL.tick = setInterval(function () {
      PL.restLeft--;
      const num = $('#plNum'); if (num) num.textContent = PL.restLeft;
      setRing(PL.restLeft, PL.restTotal);
      if (PL.restLeft <= 3 && PL.restLeft > 0) beep(880, 0.08, 0.1);
      if (PL.restLeft <= 0) { clearTick(); beep(1320, 0.18, 0.14); PL._freeRest = false; showFreeStep(PL.i + 1); }
    }, 1000);
  }
  function finishNav() {
    if (PL.isTimer) { closePlayer(); go('#/timer'); return; }
    const reached = levelReached();
    closePlayer();
    if (reached < 100) go('#/livello/' + nextLevel());
    else go('#/percorso');
  }

  /* ------------------------------------------------------------- SKILL/PR/IO */
  function toggleSkill(id, idx) {
    S.skills[id] = S.skills[id] || {};
    S.skills[id][idx] = !S.skills[id][idx];
    save();
    const sk = skills.find(s => s.id === id);
    if (sk && skillDone(sk)) toast(`⭐ Skill completata: <b>${esc(sk.name)}</b>`, true);
    const newAch = checkAch();
    newAch.forEach(av => toast(`${av.ico} Trofeo: <b>${esc(av.name)}</b>`, true));
    router();
  }
  function savePRs() {
    document.querySelectorAll('[data-pr]').forEach(inp => {
      const k = inp.getAttribute('data-pr'); const v = inp.value.trim();
      if (v === '') delete S.prs[k]; else S.prs[k] = Math.max(0, parseInt(v, 10) || 0);
    });
    save(); const na = checkAch();
    toast('✅ Record salvati');
    na.forEach(av => toast(`${av.ico} Trofeo: <b>${esc(av.name)}</b>`, true));
    updateHeader();
  }
  function doExport() {
    const box = $('#ioBox'); if (box) { box.value = JSON.stringify(S); box.select(); }
    try { navigator.clipboard && navigator.clipboard.writeText(JSON.stringify(S)); toast('📋 Backup copiato negli appunti'); }
    catch (e) { toast('Backup generato nel riquadro'); }
  }
  function doImport() {
    const box = $('#ioBox'); if (!box || !box.value.trim()) { toast('Incolla prima un backup nel riquadro'); return; }
    try {
      const data = JSON.parse(box.value.trim());
      if (!data || typeof data !== 'object') throw 0;
      S = Object.assign(defaultState(), data);
      S.settings = Object.assign(defaultState().settings, data.settings || {});
      save(); toast('✅ Backup importato'); router();
    } catch (e) { toast('❌ Backup non valido'); }
  }
  function doReset() {
    if (!confirm('Azzerare TUTTI i progressi (livelli, XP, streak, record)? Non è reversibile.')) return;
    S = defaultState(); save(); toast('Progressi azzerati'); go('#/');
  }

  /* ============================================================ INIT */
  window.addEventListener('hashchange', router);
  function init() {
    $('#appHeader').hidden = false;
    $('#bottomNav').hidden = false;
    if (!location.hash) location.hash = '#/';
    router();
    setTimeout(() => { const sp = $('#splash'); if (sp) { sp.classList.add('hide'); setTimeout(() => sp.remove(), 500); } }, 550);
    // service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
  }
  init();

})(window.CALI = window.CALI || {});
