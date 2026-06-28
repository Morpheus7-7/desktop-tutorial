/* ===========================================================
   Gin Pass — Gintoneria Club (PWA demo)
   Stato persistito in localStorage. Nessun backend.
   =========================================================== */
(() => {
  "use strict";

  const STORE_KEY = "ginpass_v1";

  /* ---------- Dati di configurazione ---------- */
  const LEVELS = [
    { name: "Apprendista", min: 0,   emoji: "🌱" },
    { name: "Gin Lover",   min: 100, emoji: "🍸" },
    { name: "Mixologist",  min: 300, emoji: "🧪" },
    { name: "Gin Master",  min: 600, emoji: "👑" },
    { name: "Leggenda",    min: 1000, emoji: "⚡" },
  ];

  const REWARDS = [
    { id: "tonica",   emoji: "🫧", name: "Tonica premium in upgrade", desc: "Passa alla tonica artigianale", cost: 80 },
    { id: "drink",    emoji: "🍸", name: "Gin Tonic omaggio",          desc: "Il classico, offre la casa",   cost: 200 },
    { id: "tagliere", emoji: "🧀", name: "Tagliere della casa",        desc: "Da condividere (o no)",        cost: 260 },
    { id: "tasting",  emoji: "🥃", name: "Tasting 3 gin guidato",      desc: "Con il nostro bartender",      cost: 450 },
    { id: "bottle",   emoji: "🍾", name: "Bottiglia a scelta -20%",    desc: "Da portare a casa",            cost: 600 },
  ];

  const BADGES = [
    { id: "first",   emoji: "🎉", name: "Prima volta",     desc: "Prima consumazione",        test: s => s.visits >= 1 },
    { id: "regular", emoji: "🔥", name: "Habitué",          desc: "5 consumazioni",            test: s => s.visits >= 5 },
    { id: "explorer",emoji: "🧭", name: "Esploratore",      desc: "Prova 3 gin diversi",       test: s => s.tasted.length >= 3 },
    { id: "night",   emoji: "🌙", name: "Nottambulo",       desc: "Check-in dopo le 23:00",    test: s => !!s.nightOwl },
    { id: "spender", emoji: "💎", name: "Top Member",       desc: "500 punti totali",          test: s => s.totalEarned >= 500 },
    { id: "redeem",  emoji: "🎁", name: "Premiato",         desc: "Riscatta un premio",        test: s => s.redeemed >= 1 },
  ];

  const GINS = [
    { emoji: "🍋", name: "Citrus Bomb", sub: "London Dry · agrumato", desc: "Esplosione di limone e pompelmo, finale secco. Il nostro best seller per chi ama il G&T fresco.", tags: ["Tonica neutra", "Rosmarino", "Pompelmo"] },
    { emoji: "🌸", name: "Botanica",    sub: "Floreale · delicato",   desc: "Fiori di sambuco e lavanda, sorso elegante e profumato. Perfetto per un aperitivo soft.", tags: ["Tonica floreale", "Lampone", "Lavanda"] },
    { emoji: "🌿", name: "Mediterraneo",sub: "Erbaceo · sapido",      desc: "Basilico, timo e oliva. Sa di estate al sud. Da provare con una tonica mediterranea.", tags: ["Tonica mediterranea", "Oliva", "Timo"] },
    { emoji: "🌶️", name: "Spicy Soul",  sub: "Speziato · intenso",    desc: "Pepe rosa e zenzero per palati audaci. Per chi vuole un G&T con carattere.", tags: ["Ginger tonic", "Pepe rosa", "Lime"] },
    { emoji: "🫐", name: "Wild Berry",  sub: "Fruttato · sloe gin",   desc: "Bacche selvatiche e mirtillo, dolce e avvolgente. Quasi un dessert.", tags: ["Tonica ai frutti", "Mirtillo", "Menta"] },
  ];

  const POINTS_PER_VISIT = 50;

  /* ---------- Stato ---------- */
  const defaultState = () => ({
    name: "",
    bday: "",
    memberId: "GTN-" + String(Math.floor(100000 + Math.random() * 900000)),
    points: 0,
    totalEarned: 0,
    visits: 0,
    redeemed: 0,
    tasted: [],
    nightOwl: false,
    activity: [],
    badges: [],
  });

  let state = load();

  function load() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) return Object.assign(defaultState(), JSON.parse(raw));
    } catch (_) {}
    return null;
  }
  function save() { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }

  /* ---------- Helpers ---------- */
  const $ = sel => document.querySelector(sel);
  const $$ = sel => Array.from(document.querySelectorAll(sel));

  function levelFor(points) {
    let cur = LEVELS[0], idx = 0;
    LEVELS.forEach((l, i) => { if (points >= l.min) { cur = l; idx = i; } });
    return { level: cur, index: idx, next: LEVELS[idx + 1] || null };
  }

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.remove("hidden");
    requestAnimationFrame(() => t.classList.add("show"));
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      t.classList.remove("show");
      setTimeout(() => t.classList.add("hidden"), 300);
    }, 2400);
  }

  function timeAgo(ts) {
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return "adesso";
    if (s < 3600) return Math.floor(s / 60) + " min fa";
    if (s < 86400) return Math.floor(s / 3600) + " h fa";
    return Math.floor(s / 86400) + " g fa";
  }

  function logActivity(emoji, text, pts) {
    state.activity.unshift({ emoji, text, pts, ts: Date.now() });
    state.activity = state.activity.slice(0, 12);
  }

  /* ---------- Render ---------- */
  function render() {
    const { level, next } = levelFor(state.points);

    $("#member-name").textContent = state.name || "Gin Lover";
    $("#points-num").textContent = state.points;
    $("#level-badge").textContent = level.emoji + " " + level.name;
    $("#member-id").textContent = state.memberId;
    $("#qr-id").textContent = state.memberId;

    // progresso verso livello successivo
    const bar = $("#progress-bar");
    if (next) {
      const span = next.min - level.min;
      const done = state.points - level.min;
      const pct = Math.max(4, Math.min(100, Math.round((done / span) * 100)));
      bar.style.width = pct + "%";
      $("#progress-text").textContent =
        `${next.min - state.points} punti a ${next.emoji} ${next.name}`;
    } else {
      bar.style.width = "100%";
      $("#progress-text").textContent = "Livello massimo raggiunto! 👑";
    }

    renderActivity();
    renderRewards();
    renderLevels();
    renderBadges();
  }

  function renderActivity() {
    const ul = $("#activity-list");
    if (!state.activity.length) {
      ul.innerHTML = `<li class="empty">Nessuna attività. Registra la tua prima consumazione! 🥃</li>`;
      return;
    }
    ul.innerHTML = state.activity.map(a => `
      <li>
        <span class="a-emoji">${a.emoji}</span>
        <span class="a-text">${a.text}<span class="a-time">${timeAgo(a.ts)}</span></span>
        ${a.pts ? `<span class="a-pts">${a.pts > 0 ? "+" : ""}${a.pts}</span>` : ""}
      </li>`).join("");
  }

  function renderRewards() {
    $("#rewards-grid").innerHTML = REWARDS.map(r => {
      const ok = state.points >= r.cost;
      return `
        <div class="reward">
          <div class="r-emoji">${r.emoji}</div>
          <div class="r-info">
            <h4>${r.name}</h4>
            <p>${r.desc}</p>
            <div class="r-cost">${r.cost} punti</div>
          </div>
          <button class="btn-redeem" data-reward="${r.id}" ${ok ? "" : "disabled"}>
            ${ok ? "Riscatta" : "🔒"}
          </button>
        </div>`;
    }).join("");
  }

  function renderLevels() {
    const { index } = levelFor(state.points);
    $("#levels-track").innerHTML = LEVELS.map((l, i) => {
      const cls = i === index ? "cur" : i < index ? "done" : "";
      let tag = "";
      if (i === index) tag = `<span class="l-tag now">Sei qui</span>`;
      else if (i < index) tag = `<span class="l-tag ok">✓</span>`;
      return `
        <div class="level-row ${cls}">
          <span class="l-emoji">${l.emoji}</span>
          <span class="l-name">${l.name}</span>
          <span class="l-req">${l.min} pt</span>
          ${tag}
        </div>`;
    }).join("");
  }

  function renderBadges() {
    $("#badges-grid").innerHTML = BADGES.map(b => {
      const earned = state.badges.includes(b.id);
      return `
        <div class="badge ${earned ? "" : "locked"}">
          ${earned ? `<span class="b-check">✓</span>` : ""}
          <div class="b-emoji">${b.emoji}</div>
          <h4>${b.name}</h4>
          <p>${b.desc}</p>
        </div>`;
    }).join("");
  }

  function renderGins() {
    $("#gin-list").innerHTML = GINS.map((g, i) => `
      <div class="gin" data-gin="${i}">
        <div class="gin-head">
          <span class="gin-emoji">${g.emoji}</span>
          <div class="g-main">
            <h4>${g.name}</h4>
            <div class="g-sub">${g.sub}</div>
          </div>
          <span class="g-arrow">▾</span>
        </div>
        <div class="gin-body">
          <p>${g.desc}</p>
          <div class="g-bot">${g.tags.map(t => `<span class="tag">${t}</span>`).join("")}</div>
        </div>
      </div>`).join("");
  }

  /* ---------- Badge / livelli: controlli a evento ---------- */
  function checkBadges() {
    const newly = [];
    BADGES.forEach(b => {
      if (!state.badges.includes(b.id) && b.test(state)) {
        state.badges.push(b.id);
        newly.push(b);
      }
    });
    newly.forEach((b, i) => setTimeout(() => toast(`${b.emoji} Badge sbloccato: ${b.name}!`), 600 + i * 900));
  }

  function checkLevelUp(prevPoints) {
    const before = levelFor(prevPoints).index;
    const after = levelFor(state.points).index;
    if (after > before) {
      const lv = LEVELS[after];
      setTimeout(() => toast(`${lv.emoji} Livello su: sei ${lv.name}!`), 300);
    }
  }

  /* ---------- Azioni ---------- */
  function checkin() {
    const prev = state.points;
    state.points += POINTS_PER_VISIT;
    state.totalEarned += POINTS_PER_VISIT;
    state.visits += 1;

    // simula la degustazione di un gin a rotazione
    const gin = GINS[state.visits % GINS.length];
    if (!state.tasted.includes(gin.name)) state.tasted.push(gin.name);

    const hour = new Date().getHours();
    if (hour >= 23 || hour < 5) state.nightOwl = true;

    logActivity("🥃", `Consumazione · ${gin.name}`, POINTS_PER_VISIT);
    save();
    checkLevelUp(prev);
    checkBadges();
    render();
    toast(`+${POINTS_PER_VISIT} punti! Salute 🍸`);
  }

  function redeem(id) {
    const r = REWARDS.find(x => x.id === id);
    if (!r || state.points < r.cost) return;
    state.points -= r.cost;
    state.redeemed += 1;
    logActivity(r.emoji, `Premio riscattato · ${r.name}`, -r.cost);
    save();
    checkBadges();
    render();
    toast(`${r.emoji} Premio riscattato! Mostralo al bancone.`);
  }

  /* ---------- QR ---------- */
  function openQr() {
    const box = $("#qr-box");
    box.innerHTML = "";
    const payload = JSON.stringify({ id: state.memberId, app: "ginpass" });
    if (window.QRCode) {
      new window.QRCode(box, { text: payload, width: 180, height: 180, correctLevel: window.QRCode.CorrectLevel.M });
    } else {
      box.innerHTML = `<div class="qr-fallback">${state.memberId}</div>`;
    }
    $("#qr-modal").classList.remove("hidden");
  }
  function closeQr() { $("#qr-modal").classList.add("hidden"); }

  /* ---------- Navigazione tab ---------- */
  function goTab(name) {
    $$(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + name));
    $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- Onboarding ---------- */
  function startApp() {
    $("#onboarding").classList.add("hidden");
    $("#app").classList.remove("hidden");
    renderGins();
    render();
  }

  function initOnboarding() {
    $("#onboarding").classList.remove("hidden");
    $("#signup-form").addEventListener("submit", e => {
      e.preventDefault();
      const name = $("#name-input").value.trim();
      if (!name) return;
      state = defaultState();
      state.name = name;
      state.bday = $("#bday-input").value || "";
      logActivity("✨", "Benvenuto nel club!", 0);
      // bonus di benvenuto
      state.points = 20; state.totalEarned = 20;
      logActivity("🎁", "Bonus di benvenuto", 20);
      save();
      startApp();
      setTimeout(() => toast("Benvenuto! +20 punti regalo 🎉"), 500);
    });
  }

  /* ---------- PWA install ---------- */
  let deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", e => {
    e.preventDefault();
    deferredPrompt = e;
    $("#install-btn").classList.remove("hidden");
  });
  function setupInstall() {
    $("#install-btn").addEventListener("click", async () => {
      if (!deferredPrompt) { toast("Usa il menu del browser → 'Aggiungi a Home'"); return; }
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      $("#install-btn").classList.add("hidden");
    });
  }

  /* ---------- Event delegation ---------- */
  function bindEvents() {
    $("#checkin-btn").addEventListener("click", checkin);
    $("#show-qr").addEventListener("click", openQr);
    $("#qr-close").addEventListener("click", closeQr);
    $("#qr-modal").addEventListener("click", e => { if (e.target.id === "qr-modal") closeQr(); });

    document.body.addEventListener("click", e => {
      const nav = e.target.closest(".nav-btn");
      if (nav) return goTab(nav.dataset.tab);

      const goto = e.target.closest("[data-goto]");
      if (goto) return goTab(goto.dataset.goto);

      const rdm = e.target.closest("[data-reward]");
      if (rdm && !rdm.disabled) return redeem(rdm.dataset.reward);

      const gin = e.target.closest(".gin");
      if (gin) gin.classList.toggle("open");
    });
  }

  /* ---------- Boot ---------- */
  function boot() {
    bindEvents();
    setupInstall();
    if (state && state.name) {
      startApp();
    } else {
      initOnboarding();
    }
  }

  document.addEventListener("DOMContentLoaded", boot);

  // Service worker
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();
