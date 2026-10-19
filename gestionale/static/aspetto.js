/* Modalità chiara/scura: applicata prima del disegno della pagina (niente
   lampo bianco). «auto» segue l'impostazione di Windows. */
(function () {
  'use strict';
  var radice = document.documentElement;
  var scelta = radice.getAttribute('data-aspetto') || 'auto';
  var scuro = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
  function applica() {
    var tema = scelta === 'auto' ? (scuro && scuro.matches ? 'dark' : 'light') : (scelta === 'scuro' ? 'dark' : 'light');
    radice.setAttribute('data-bs-theme', tema);
  }
  applica();
  if (scelta === 'auto' && scuro && scuro.addEventListener) scuro.addEventListener('change', applica);
})();
