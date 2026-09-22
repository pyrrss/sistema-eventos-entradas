import { api } from './api.js';

let modalRoot = null;
let modalTitle = null;
let modalBody = null;
let confirmRoot = null;

export function initUi() {
  modalRoot = document.getElementById('app-modal');
  modalTitle = document.getElementById('modal-title');
  modalBody = document.getElementById('modal-body');
  confirmRoot = document.getElementById('confirm-modal');

  const modalClose = document.getElementById('modal-close');
  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modalRoot) modalRoot.addEventListener('click', (e) => {
    if (e.target === modalRoot) closeModal();
  });
  const pill = document.querySelector('[data-role="api-pill"]');
  if (pill) pill.addEventListener('click', checkApi);
}

async function checkApi() {
  const pill = document.querySelector('[data-role="api-pill"]');
  const text = pill?.querySelector('.api-pill__text');
  if (!pill || !text) return;
  pill.disabled = true;
  text.textContent = 'Verificando...';
  try {
    await api.health();
    setApiStatus(true);
    toast('La API de venta esta en linea');
  } catch (err) {
    setApiStatus(false);
    toast(err.message, 'error');
  } finally {
    pill.disabled = false;
  }
}

export function toast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = 'toast' + (type === 'error' ? ' toast--error' : '');
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');

  const icon = document.createElement('span');
  icon.className = 'toast__icon';
  icon.innerHTML = '<svg width="15" height="15" aria-hidden="true"><use href="#' + (type === 'error' ? 'i-alert' : 'i-check') + '"/></svg>';
  const text = document.createElement('span');
  text.textContent = message;
  el.append(icon, text);
  container.appendChild(el);

  setTimeout(() => {
    el.classList.add('toast--out');
    setTimeout(() => el.remove(), 320);
  }, 3600);
}

export function openModal(title, contentNode) {
  if (!modalTitle || !modalBody || !modalRoot) return;
  modalTitle.textContent = title;
  modalBody.innerHTML = '';
  modalBody.appendChild(contentNode);
  if (!modalRoot.open) modalRoot.showModal();
}

export function closeModal() {
  if (modalRoot?.open) modalRoot.close();
}

export function confirmDialog({ title, message, confirmText }) {
  return new Promise((resolve) => {
    const confirmTitle = document.getElementById('confirm-title');
    const confirmMessage = document.getElementById('confirm-message');
    const ok = document.getElementById('confirm-ok');
    const cancel = document.getElementById('confirm-cancel');
    const confirmRootEl = document.getElementById('confirm-modal');
    if (!confirmTitle || !confirmMessage || !ok || !cancel || !confirmRootEl) {
      resolve(false);
      return;
    }
    confirmTitle.textContent = title;
    confirmMessage.textContent = message;
    ok.textContent = confirmText;

    const cleanup = () => {
      cancel.removeEventListener('click', onDismiss);
      ok.removeEventListener('click', onConfirm);
      confirmRootEl.removeEventListener('cancel', onDismiss);
    };
    const onDismiss = () => {
      cleanup();
      if (confirmRootEl.open) confirmRootEl.close();
      resolve(false);
    };
    const onConfirm = () => {
      cleanup();
      confirmRootEl.close();
      resolve(true);
    };

    cancel.addEventListener('click', onDismiss);
    ok.addEventListener('click', onConfirm);
    confirmRootEl.addEventListener('cancel', onDismiss);
    confirmRootEl.showModal();
    cancel.focus();
  });
}

export function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll("\"", "&quot;")
    .replaceAll("'", '&#39;');
}

export function dlNode(entries) {
  const dl = document.createElement('dl');
  dl.className = 'dl';
  for (const [label, value] of entries) {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value ?? '\u2014';
    dl.appendChild(dt);
    dl.appendChild(dd);
  }
  return dl;
}

export function setApiStatus(online) {
  const pill = document.querySelector('[data-role="api-pill"]');
  if (!pill) return;
  pill.classList.remove('is-unknown');
  pill.classList.toggle('is-offline', !online);
  const text = pill.querySelector('.api-pill__text');
  if (text) text.textContent = online ? 'API en linea' : 'API sin respuesta';
  pill.title = online
    ? 'Ultima verificacion: la API de venta respondio correctamente'
    : 'Ultima verificacion: no se pudo contactar la API de venta. Clic para reintentar';
}

export function icon(name, size = 15) {
  return '<svg width="' + size + '" height="' + size + '" aria-hidden="true"><use href="#' + name + '"/></svg>';
}
