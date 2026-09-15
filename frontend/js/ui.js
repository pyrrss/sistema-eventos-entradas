let toastTimer = 0;

export function initUi() {
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-root').addEventListener('click', (e) => {
    if (e.target.id === 'modal-root') closeModal();
  });
}

export function toast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = message;
  container.appendChild(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    container.querySelectorAll('.toast').forEach((t) => {
      t.classList.add('toast--out');
      setTimeout(() => t.remove(), 300);
    });
  }, 3000);
}

export function openModal(title, contentNode) {
  document.getElementById('modal-title').textContent = title;
  const body = document.getElementById('modal-body');
  body.innerHTML = '';
  body.appendChild(contentNode);
  document.getElementById('modal-root').classList.remove('is-hidden');
}

export function closeModal() {
  document.getElementById('modal-root').classList.add('is-hidden');
}

export function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function dlNode(entries) {
  const dl = document.createElement('dl');
  dl.className = 'dl';
  for (const [label, value] of entries) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value ?? '—';
    dl.appendChild(dt);
    dl.appendChild(dd);
  }
  return dl;
}