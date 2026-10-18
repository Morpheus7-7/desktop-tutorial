/* Gestionale Assicurativo — comportamenti comuni dell'interfaccia. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    // --- Schede (tab): apre quella indicata nell'ancora (#polizze) o, in sua
    // assenza, quella richiesta dal server (es. dopo un errore di validazione).
    const iniziale = document.querySelector('[data-tab-iniziale]');
    const hash = window.location.hash.replace('#', '') || (iniziale ? iniziale.dataset.tabIniziale : '');
    if (hash) {
      const trigger = document.querySelector('[data-bs-target="#tab-' + hash + '"]');
      if (trigger && window.bootstrap) new bootstrap.Tab(trigger).show();
    }
    document.querySelectorAll('[data-bs-toggle="tab"][data-bs-target^="#tab-"]').forEach(function (el) {
      el.addEventListener('shown.bs.tab', function () {
        const nome = el.getAttribute('data-bs-target').replace('#tab-', '');
        history.replaceState(null, '', '#' + nome);
      });
    });

    // --- Conferma prima di inviare i form distruttivi: <form data-confirm="...">
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.confirm(form.getAttribute('data-confirm'))) e.preventDefault();
      });
    });

    // --- Stampa e invio automatico dei filtri (niente script inline: CSP).
    document.querySelectorAll('[data-print]').forEach(function (btn) {
      btn.addEventListener('click', function () { window.print(); });
    });
    document.querySelectorAll('[data-autosubmit]').forEach(function (campo) {
      campo.addEventListener('change', function () {
        if (campo.form) {
          if (campo.form.requestSubmit) campo.form.requestSubmit();
          else campo.form.submit();
        }
      });
    });

    // --- Limiti predefiniti dei campi data (1900–2100), come sul server.
    document.querySelectorAll('input[type="date"]').forEach(function (campo) {
      if (!campo.min) campo.min = '1900-01-01';
      if (!campo.max) campo.max = '2100-12-31';
    });

    // --- Modali con azione variabile: <button data-bs-toggle="modal" data-action="url" data-fill-xxx="...">
    document.querySelectorAll('.modal[data-dynamic]').forEach(function (modal) {
      modal.addEventListener('show.bs.modal', function (e) {
        const btn = e.relatedTarget;
        if (!btn) return;
        const form = modal.querySelector('form');
        // Ogni apertura parte dai valori predefiniti (data di oggi, mezzo e
        // riferimento vuoti): nessun dato resta dal titolo precedente.
        form.reset();
        delete form.dataset.inviato;
        form.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
        if (btn.dataset.action) form.setAttribute('action', btn.dataset.action);
        Object.keys(btn.dataset).forEach(function (key) {
          if (!key.startsWith('fill')) return;
          const nome = key.slice(4).replace(/^[A-Z]/, function (c) { return c.toLowerCase(); });
          modal.querySelectorAll('[data-field="' + nome + '"]').forEach(function (campo) {
            if ('value' in campo && campo.tagName !== 'SPAN' && campo.tagName !== 'DIV') campo.value = btn.dataset[key];
            else campo.textContent = btn.dataset[key];
          });
        });
      });
    });

    // --- Modulo cliente: mostra solo i campi pertinenti al tipo (data-tipi) e
    // adatta etichette e suggerimenti (data-testo-*, data-placeholder-*). I
    // campi nascosti vengono disattivati, così non sono inviati né validati.
    const tipoCliente = document.getElementById('tipo-cliente');
    if (tipoCliente) {
      const modulo = tipoCliente.form;
      const campoProfessione = document.getElementById('cf-professione');
      const infoProfessione = document.getElementById('info-professione');
      const campoAlbo = document.getElementById('cf-albo');
      let catalogo = [];
      try { catalogo = JSON.parse((campoProfessione && campoProfessione.dataset.catalogo) || '[]'); } catch (e) { catalogo = []; }

      const normalizza = function (testo) {
        return (testo || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
          .replace(/\s+/g, ' ').trim();
      };
      const escapeRegExp = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
      // Stesse regole del server (professioni.trova_professione): vince la
      // professione nominata per prima, a parità l'alias più lungo; il medico
      // nominato in modo generico cede alla specialità medica («Medico pediatra»).
      const trovaProfessione = function (testo) {
        const n = normalizza((testo || '').slice(0, 200));
        if (!n) return null;
        const candidati = [];
        catalogo.forEach(function (p, indice) {
          let migliore = null;
          p.alias.forEach(function (a) {
            if (!a) return;
            const m = new RegExp('(^|[^a-z0-9])' + escapeRegExp(a)).exec(n);
            if (!m) return;
            const voto = [m.index + m[1].length, -a.length, a];
            if (!migliore || voto[0] < migliore[0] || (voto[0] === migliore[0] && voto[1] < migliore[1])) migliore = voto;
          });
          if (migliore) candidati.push([migliore[0], migliore[1], indice, p, migliore[2]]);
        });
        if (!candidati.length) return null;
        candidati.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] || a[2] - b[2]; });
        let scelta = candidati[0][3];
        if (scelta.alias_generici.indexOf(candidati[0][4]) !== -1) {
          const specifica = candidati.find(function (c) { return scelta.cede_a.indexOf(c[3].chiave) !== -1; });
          if (specifica) scelta = specifica[3];
        }
        return scelta;
      };

      const aggiornaAbilitati = function () {
        modulo.querySelectorAll('input, select, textarea').forEach(function (campo) {
          if (campo === tipoCliente || campo.type === 'hidden') return;
          campo.disabled = campo.closest('[hidden]') !== null;
        });
      };

      const aggiornaProfessione = function () {
        if (!campoProfessione) return;
        const tipo = tipoCliente.value;
        const attiva = tipo === 'studio' || tipo === 'professionista';
        const p = attiva ? trovaProfessione(campoProfessione.value) : null;
        modulo.querySelectorAll('.gruppo-professione').forEach(function (gruppo) {
          gruppo.hidden = !p || gruppo.dataset.professione !== p.chiave;
        });
        if (infoProfessione) {
          infoProfessione.textContent = p ? p.info
            : (campoProfessione.value.trim()
              ? 'Professione non in elenco: indica specializzazioni e attività nei campi «Altre».'
              : 'Scegli dall\'elenco o scrivi la professione: compariranno specializzazioni e attività da selezionare.');
        }
        if (campoAlbo) campoAlbo.placeholder = p && p.albo ? p.albo + ' di …' : 'es. Ordine degli Avvocati di Milano';
        aggiornaAbilitati();
      };

      const aggiornaTipo = function () {
        const tipo = tipoCliente.value;
        const suffisso = tipo.charAt(0).toUpperCase() + tipo.slice(1);
        modulo.querySelectorAll('[data-tipi]').forEach(function (el) {
          el.hidden = el.dataset.tipi.split(' ').indexOf(tipo) === -1;
        });
        modulo.querySelectorAll('[data-testo]').forEach(function (el) {
          el.textContent = el.dataset['testo' + suffisso] || el.dataset.testo;
        });
        modulo.querySelectorAll('[data-placeholder]').forEach(function (el) {
          el.placeholder = el.dataset['placeholder' + suffisso] || el.dataset.placeholder;
        });
        aggiornaProfessione();
      };
      tipoCliente.addEventListener('change', aggiornaTipo);
      if (campoProfessione) campoProfessione.addEventListener('input', aggiornaProfessione);
      aggiornaTipo();
    }

    // --- Menu a tendina dipendenti (es. polizze filtrate per cliente).
    document.querySelectorAll('select[data-filter-target]').forEach(function (sorgente) {
      const target = document.querySelector(sorgente.dataset.filterTarget);
      if (!target) return;
      function filtra() {
        const valore = sorgente.value;
        target.querySelectorAll('option[data-parent]').forEach(function (opt) {
          const visibile = !valore || opt.dataset.parent === valore;
          opt.hidden = !visibile;
          opt.disabled = !visibile;
          if (!visibile && opt.selected) target.value = '';
        });
      }
      sorgente.addEventListener('change', filtra);
      filtra();
    });

    // --- Dropzone per il caricamento documenti (drag & drop + anteprima).
    document.querySelectorAll('.dropzone[data-input]').forEach(function (dz) {
      const input = document.getElementById(dz.dataset.input);
      const lista = document.getElementById(dz.dataset.list);
      if (!input) return;
      const fmt = function (b) {
        return b < 1024 ? b + ' B' : (b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB');
      };
      function mostra() {
        if (!lista) return;
        lista.innerHTML = '';
        Array.from(input.files).forEach(function (f) {
          const pill = document.createElement('span');
          pill.className = 'file-pill';
          const icona = document.createElement('i');
          icona.className = 'bi bi-paperclip';
          const nome = document.createElement('span');
          nome.textContent = f.name + ' (' + fmt(f.size) + ')';
          pill.appendChild(icona);
          pill.appendChild(nome);
          lista.appendChild(pill);
        });
      }
      dz.addEventListener('click', function () { input.click(); });
      dz.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
      input.addEventListener('change', mostra);
      ['dragover', 'dragenter'].forEach(function (ev) {
        dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('dragover'); });
      });
      ['dragleave', 'drop'].forEach(function (ev) {
        dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('dragover'); });
      });
      dz.addEventListener('drop', function (e) { input.files = e.dataTransfer.files; mostra(); });
    });
  });

  // --- Niente doppio invio: un secondo clic su «Salva», «Incassa», «Rinnova»…
  // non ripete l'operazione. Gestito sul documento, dopo le conferme dei form.
  document.addEventListener('submit', function (e) {
    const form = e.target;
    if (e.defaultPrevented || (form.getAttribute('method') || 'get').toLowerCase() !== 'post') return;
    if (form.dataset.inviato) { e.preventDefault(); return; }
    form.dataset.inviato = '1';
    setTimeout(function () {
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach(function (b) { b.disabled = true; });
    }, 0);
    // Download (es. backup) o risposta lenta: si riabilita dopo qualche secondo.
    setTimeout(function () {
      delete form.dataset.inviato;
      form.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
    }, 8000);
  });
  // Tornando indietro (cache del browser) i pulsanti devono essere di nuovo attivi.
  window.addEventListener('pageshow', function () {
    document.querySelectorAll('form[data-inviato]').forEach(function (form) {
      delete form.dataset.inviato;
      form.querySelectorAll('button').forEach(function (b) { b.disabled = false; });
    });
  });
})();
