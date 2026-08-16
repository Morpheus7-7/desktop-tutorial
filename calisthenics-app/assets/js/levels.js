/* ============================================================================
 * Cali100 — Generatore delle 100 schede progressive (da 0 a 100)
 *
 * Ogni livello è costruito in modo deterministico dai dati di data.js:
 *   - la difficoltà bersaglio cresce con il numero del livello,
 *   - gli esercizi vengono scelti dalle "scale" (ladder) per pattern,
 *   - serie/ripetizioni/tenute e recuperi scalano per fase e micro-ciclo,
 *   - il focus ruota (full-body / upper / lower / skill) per varietà.
 * Il risultato è salvato in CALI.levels come array di 100 schede.
 * ==========================================================================*/
(function (CALI) {
  'use strict';

  const byId = CALI.exById;

  // Scale di progressione per pattern (id ordinati poi per difficoltà).
  const LAD = {
    push:   ['wall_pushup','incline_pushup','knee_pushup','pushup','wide_pushup','diamond_pushup','archer_pushup','pseudo_planche_pushup'],
    vpush:  ['pike_pushup','decline_pushup','elevated_pike_pushup','wall_hspu'],
    dip:    ['bench_dip','parallel_dip'],
    pull:   ['superman_hold','dead_hang','scapular_pull','table_row','inverted_row_bar','negative_pullup','assisted_pullup','pullup','chinup','wide_pullup','archer_pullup'],
    row:    ['prone_ytw','superman_hold','towel_row','table_row','inverted_row_bar'],
    hinge:  ['glute_bridge','single_leg_glute_bridge','sliding_leg_curl','nordic_curl_negative'],
    squat:  ['squat','split_squat','reverse_lunge','bulgarian_split_squat','cossack_squat','assisted_pistol','box_pistol','pistol_squat','shrimp_squat'],
    legpow: ['calf_raise','single_calf_raise','squat_jump','broad_jump'],
    core:   ['dead_bug','bird_dog','plank','hollow_hold','side_plank','lying_leg_raise','hollow_rock','v_up','tuck_lsit','hanging_leg_raise','dragon_flag_negative','dragon_flag'],
    coredyn:['mountain_climbers','bicycle_crunch','russian_twist','flutter_kicks','plank_shoulder_tap','reverse_crunch'],
    skpush: ['planche_lean','frog_stand','wall_walk','wall_handstand_hold','tuck_planche','chest_wall_handstand','adv_tuck_planche','straddle_planche','freestanding_handstand','full_planche'],
    skpull: ['tuck_fl','adv_tuck_fl','muscleup_transition','straddle_fl','muscleup','full_fl'],
  };
  // Ordina ogni scala per difficoltà crescente e rimuove id inesistenti.
  Object.keys(LAD).forEach(function (k) {
    LAD[k] = LAD[k].map(function (id) { return byId[id]; })
                   .filter(Boolean)
                   .sort(function (a, b) { return a.diff - b.diff; });
  });

  // Finestra di difficoltà consentita per fase (evita salti irrealistici).
  const PHASE_CLAMP = {
    fondamenta: [1, 3], costruzione: [2, 5], forza: [4, 7], avanzato: [5, 9], elite: [6, 10],
  };

  // Template di seduta per fase: liste di slot {lad, role}. role: main|acc|skill.
  const TPL = {
    fondamenta: [
      [{lad:'push',role:'main'},{lad:'squat',role:'main'},{lad:'pull',role:'main'},{lad:'core',role:'main'}],
      [{lad:'push',role:'main'},{lad:'hinge',role:'acc'},{lad:'coredyn',role:'acc'},{lad:'core',role:'main'}],
      [{lad:'squat',role:'main'},{lad:'pull',role:'main'},{lad:'legpow',role:'acc'},{lad:'core',role:'main'}],
    ],
    costruzione: [
      [{lad:'push',role:'main'},{lad:'pull',role:'main'},{lad:'squat',role:'main'},{lad:'core',role:'main'},{lad:'coredyn',role:'acc'}],
      [{lad:'push',role:'main'},{lad:'vpush',role:'acc'},{lad:'pull',role:'main'},{lad:'dip',role:'acc'},{lad:'core',role:'main'}],
      [{lad:'squat',role:'main'},{lad:'hinge',role:'main'},{lad:'legpow',role:'acc'},{lad:'core',role:'main'},{lad:'coredyn',role:'acc'}],
    ],
    forza: [
      [{lad:'push',role:'main'},{lad:'pull',role:'main'},{lad:'vpush',role:'main'},{lad:'row',role:'acc'},{lad:'core',role:'main'}],
      [{lad:'squat',role:'main'},{lad:'hinge',role:'main'},{lad:'legpow',role:'acc'},{lad:'core',role:'main'},{lad:'coredyn',role:'acc'}],
      [{lad:'push',role:'main'},{lad:'pull',role:'main'},{lad:'squat',role:'main'},{lad:'dip',role:'acc'},{lad:'core',role:'main'}],
    ],
    avanzato: [
      [{lad:'push',role:'main'},{lad:'pull',role:'main'},{lad:'vpush',role:'main'},{lad:'row',role:'acc'},{lad:'core',role:'main'}],
      [{lad:'squat',role:'main'},{lad:'hinge',role:'main'},{lad:'legpow',role:'acc'},{lad:'core',role:'main'},{lad:'coredyn',role:'acc'}],
      [{lad:'skpush',role:'skill'},{lad:'push',role:'main'},{lad:'pull',role:'main'},{lad:'core',role:'main'}],
    ],
    elite: [
      [{lad:'skpush',role:'skill'},{lad:'push',role:'main'},{lad:'skpull',role:'skill'},{lad:'pull',role:'main'},{lad:'core',role:'main'}],
      [{lad:'skpush',role:'skill'},{lad:'pull',role:'main'},{lad:'squat',role:'main'},{lad:'core',role:'main'}],
      [{lad:'squat',role:'main'},{lad:'hinge',role:'main'},{lad:'skpull',role:'skill'},{lad:'core',role:'main'}],
    ],
  };

  const WARM_CARDIO = ['spot_jog','jumping_jacks','high_knees','butt_kicks'];
  const WARM_DYN    = ['arm_circles','leg_swings','hip_circles','torso_twists','shoulder_swings','cat_cow','inchworm','scap_pushup','ankle_rocks','deep_squat_hold'];
  const COOLDOWN    = ['child_pose','cobra_stretch','hamstring_stretch','quad_stretch','chest_doorway','pigeon_stretch','shoulder_stretch','calf_stretch','seated_twist'];

  function phaseOf(n) {
    return CALI.phases.find(function (p) { return n >= p.from && n <= p.to; });
  }

  // Difficoltà bersaglio: 1 al livello 1, 10 al livello 100.
  function targetDiff(n) { return 1 + (n - 1) * 9 / 99; }

  // Sceglie dalla scala un esercizio dentro una finestra di difficoltà attorno
  // al bersaglio, ruotando per livello per dare varietà pur restando progressivo.
  function pick(ladKey, td, n, salt) {
    const arr = LAD[ladKey];
    if (!arr || !arr.length) return null;
    let cands = arr.filter(function (e) { return e.diff >= td - 1.25 && e.diff <= td + 0.5; });
    if (!cands.length) {
      // Nessuno nella finestra: prendi il più vicino (<= td+0.5), altrimenti il più facile.
      let chosen = arr[0];
      for (let i = 0; i < arr.length; i++) { if (arr[i].diff <= td + 0.5) chosen = arr[i]; }
      cands = [chosen];
    }
    return cands[(n + (salt || 0)) % cands.length];
  }

  // Dosaggio (ripetizioni / tenuta / durata) in base al micro-ciclo.
  function dose(ex, n) {
    const wave = (n - 1) % 5;            // 0..4 dentro il micro-ciclo
    const frac = wave / 4;               // 0 -> min, 1 -> max
    if (ex.type === 'hold') {
      const r = ex.hold || [15, 30];
      // Per le skill molto dure il bersaglio resta nella metà bassa del range.
      const f = ex.diff >= 8 ? Math.min(frac, 0.5) : frac;
      return { unit: 'hold', value: Math.round(r[0] + f * (r[1] - r[0])) };
    }
    if (ex.type === 'cardio') {
      const r = ex.dur || [30, 45];
      return { unit: 'cardio', value: Math.round(r[0] + frac * (r[1] - r[0])) };
    }
    const r = ex.rep || [8, 12];
    return { unit: 'reps', value: Math.round(r[0] + frac * (r[1] - r[0])) };
  }

  function setsFor(phaseId, role) {
    if (role === 'skill') return phaseId === 'elite' ? 5 : 4;
    const map = {
      fondamenta: { main: 3, acc: 2 },
      costruzione:{ main: 4, acc: 3 },
      forza:      { main: 4, acc: 3 },
      avanzato:   { main: 4, acc: 3 },
      elite:      { main: 4, acc: 3 },
    };
    return (map[phaseId] || map.forza)[role === 'acc' ? 'acc' : 'main'];
  }

  function restFor(ex, role) {
    if (role === 'skill') {
      return ex.diff >= 8 ? 120 : 90;
    }
    let r;
    const d = ex.diff;
    if (d <= 2) r = 45; else if (d <= 4) r = 60; else if (d <= 6) r = 75; else if (d <= 8) r = 105; else r = 150;
    if (ex.cat === 'core' && ex.type !== 'hold') r = Math.min(r, 45);
    if (role === 'acc') r = Math.max(30, r - 15);
    return r;
  }

  function rot(arr, i) { return arr[i % arr.length]; }

  function buildWarmup(n) {
    const ids = [
      rot(WARM_CARDIO, n),
      rot(WARM_DYN, n),
      rot(WARM_DYN, n + 3),
      'wrist_prep',
    ];
    // dedup mantenendo l'ordine
    const seen = {}; const out = [];
    ids.forEach(function (id) { if (byId[id] && !seen[id]) { seen[id] = 1; out.push(id); } });
    return out;
  }

  function buildCooldown(n) {
    const ids = [rot(COOLDOWN, n), rot(COOLDOWN, n + 3), rot(COOLDOWN, n + 6)];
    const seen = {}; const out = [];
    ids.forEach(function (id) { if (byId[id] && !seen[id]) { seen[id] = 1; out.push(id); } });
    return out;
  }

  function buildBlocks(n, phase) {
    const templates = TPL[phase.id];
    const idxInPhase = n - phase.from;
    const template = templates[idxInPhase % templates.length];
    const clamp = PHASE_CLAMP[phase.id];
    const td = Math.min(clamp[1], Math.max(clamp[0], targetDiff(n)));
    const used = {};
    const blocks = [];

    template.forEach(function (slot, slotIdx) {
      let effTd = td;
      if (slot.role === 'acc') effTd = Math.max(clamp[0], td - 1.5);
      let ex = pick(slot.lad, effTd, n, slotIdx * 2 + 1);
      if (!ex) return;
      // Evita ripetere lo stesso esercizio: prova la progressione o regressione.
      if (used[ex.id]) {
        const alt = (ex.prog && byId[ex.prog]) || (ex.reg && byId[ex.reg]);
        if (alt && !used[alt.id]) ex = alt;
      }
      if (used[ex.id]) return;
      used[ex.id] = 1;

      const d = dose(ex, n);
      const sets = setsFor(phase.id, slot.role);
      blocks.push({
        ex: ex.id,
        sets: sets,
        unit: d.unit,
        value: d.value,
        rest: restFor(ex, slot.role),
        role: slot.role,
        uni: !!ex.uni,
      });
    });
    return blocks;
  }

  function estMinutes(warmup, blocks, cooldown) {
    let sec = warmup.length * 45 + cooldown.length * 40;
    blocks.forEach(function (b) {
      const work = b.unit === 'reps' ? (b.uni ? b.value * 2 : b.value) * 3 : b.value; // ~3s/rep
      sec += b.sets * (work + b.rest);
    });
    return Math.max(12, Math.round(sec / 60));
  }

  function titleFor(n, phase, blocks) {
    // Etichetta il focus dominante della seduta.
    const cats = blocks.map(function (b) { return byId[b.ex].cat; });
    const hasSkill = blocks.some(function (b) { return b.role === 'skill'; });
    const push = cats.filter(function (c) { return c === 'push'; }).length;
    const pull = cats.filter(function (c) { return c === 'pull'; }).length;
    const legs = cats.filter(function (c) { return c === 'legs'; }).length;
    let focus;
    if (hasSkill) focus = 'Skill & Forza';
    else if (legs >= 2) focus = 'Gambe & Core';
    else if (push + pull >= 3 && legs === 0) focus = 'Parte Alta';
    else focus = 'Full Body';
    return { focus: focus };
  }

  function xpFor(n, phase, est) {
    // XP cresce con livello e durata; bonus a fine fase.
    let xp = 80 + Math.round((n - 1) * 3) + est * 2;
    if (n === phase.to) xp += 150; // completamento fase
    return xp;
  }

  function build() {
    const levels = [];
    for (let n = 1; n <= 100; n++) {
      const phase = phaseOf(n);
      const warmup = buildWarmup(n);
      const blocks = buildBlocks(n, phase);
      const cooldown = buildCooldown(n);
      const est = estMinutes(warmup, blocks, cooldown);
      const t = titleFor(n, phase, blocks);
      const isTest = (n % 5 === 0); // ogni 5 livelli: seduta di consolidamento
      levels.push({
        n: n,
        phase: phase.id,
        phaseName: phase.name,
        phaseColor: phase.color,
        focus: t.focus,
        title: 'Livello ' + n + ' · ' + t.focus,
        est: est,
        milestone: isTest,
        warmup: warmup,
        blocks: blocks,
        cooldown: cooldown,
        xp: xpFor(n, phase, est),
      });
    }
    return levels;
  }

  CALI.levels = build();
  CALI.phaseOf = phaseOf;

})(window.CALI = window.CALI || {});
