import { initAsistentes } from './asistentes.js';
import { initVentas } from './ventas.js';
import { initUi } from './ui.js';

const views = {};

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t) => {
    t.classList.toggle('is-active', t.dataset.tab === name);
  });
  Object.entries(views).forEach(([key, view]) => {
    document.getElementById(`view-${key}`).classList.toggle('is-hidden', key !== name);
  });
  views[name].refresh();
}

document.addEventListener('DOMContentLoaded', () => {
  initUi();
  views.asistentes = initAsistentes(document.getElementById('view-asistentes'));
  views.ventas = initVentas(document.getElementById('view-ventas'));

  document.querySelectorAll('.tab').forEach((t) => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
  });

  switchTab('ventas');
});