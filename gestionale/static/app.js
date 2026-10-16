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

    // --- Modulo cliente: mostra solo i campi pertinenti al tipo. I campi
    // nascosti vengono disattivati, così non sono inviati né validati.
    const tipoCliente = document.getElementById('tipo-cliente');
    if (tipoCliente) {
      const etichettaNome = document.getElementById('label-nome');
      const aggiornaTipo = function () {
        const tipo = tipoCliente.value;
        const regole = {
          'campo-azienda': tipo === 'azienda',
          'campo-piva': tipo !== 'dipendente',
          'campo-professionista': tipo === 'professionista',
          'campo-dipendente': tipo === 'dipendente',
          'campo-impresa': tipo === 'azienda' || tipo === 'professionista',
          'campo-persona': tipo !== 'azienda'
        };
        Object.keys(regole).forEach(function (cls) {
          document.querySelectorAll('.' + cls).forEach(function (el) {
            el.style.display = regole[cls] ? '' : 'none';
            el.querySelectorAll('input, select, textarea').forEach(function (campo) { campo.disabled = !regole[cls]; });
          });
        });
        if (etichettaNome) {
          etichettaNome.textContent = tipo === 'azienda'
            ? 'Ragione sociale *'
            : (tipo === 'dipendente' ? 'Nome e cognome *' : 'Nominativo *');
        }
      };
      tipoCliente.addEventListener('change', aggiornaTipo);
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
