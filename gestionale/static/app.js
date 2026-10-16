/* Gestionale Assicurativo — comportamenti comuni dell'interfaccia. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    // --- Schede (tab): apre quella indicata nell'ancora (#polizze) e la ricorda.
    const hash = window.location.hash.replace('#', '');
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

    // --- Modali con azione variabile: <button data-bs-toggle="modal" data-action="url" data-fill-xxx="...">
    document.querySelectorAll('.modal[data-dynamic]').forEach(function (modal) {
      modal.addEventListener('show.bs.modal', function (e) {
        const btn = e.relatedTarget;
        if (!btn) return;
        const form = modal.querySelector('form');
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
})();
