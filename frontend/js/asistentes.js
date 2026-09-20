import { api } from './api.js';
import { esc, toast, openModal, closeModal, dlNode, icon } from './ui.js';

const TEMPLATE = `
  <div class="view-head">
    <div class="view-head__titles">
      <h2>Asistentes</h2>
      <span class="count-stamp" data-role="asistentes:count"></span>
    </div>
    <div class="view-head__actions">
      <button class="btn btn--primary" data-role="asistentes:new" type="button">
        ${icon('i-user', 14)} Nuevo asistente
      </button>
    </div>
  </div>

  <div class="card">
    <div class="card__band">
      <span class="card__band-title">${icon('i-users', 15)} Registro de asistentes</span>
      <span class="station__hint">Cada asistente puede adquirir entradas en cualquier evento</span>
    </div>
    <div class="perfo"></div>
    <div data-role="asistentes:state"></div>
    <div class="table-wrap" data-role="asistentes:table-wrap">
      <table class="table table--two">
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Nombre</th>
            <th scope="col">RUT</th>
            <th scope="col">Correo</th>
            <th scope="col"><span class="sr-label">Acciones</span></th>
          </tr>
        </thead>
        <tbody data-role="asistentes:tbody"></tbody>
      </table>
    </div>
  </div>
`;

const EMPTY_HTML = `
  <div class="empty">
    <svg class="empty__art" width="56" height="56" viewBox="0 0 24 24" aria-hidden="true">
      <use href="#i-users" />
    </svg>
    <h3 class="empty__title">Nadie en la lista todavía</h3>
    <p class="empty__text">Registra tu primer asistente para poder venderle entradas desde la ventanilla.</p>
    <button class="btn btn--primary" type="button" data-role="asistentes:empty-new">Nuevo asistente</button>
  </div>
`;

function initials(nombre) {
  const parts = String(nombre || '?').trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

function shortId(id) {
  return `#${String(id || '?').slice(0, 8)}`;
}

function buildForm() {
  const form = document.createElement('form');
  form.className = 'sale';
  form.noValidate = true;
  form.innerHTML = `
    <label class="field" style="margin-bottom:12px">
      <span>RUT</span>
      <input class="input" name="rut" required autocomplete="off" placeholder="Ej. 12.345.678-9" />
      <span class="field__error">${icon('i-alert', 13)} Ingresa un RUT válido (ej. 12345678-9).</span>
    </label>
    <label class="field" style="margin-bottom:12px">
      <span>Nombre completo</span>
      <input class="input" name="nombre_completo" required autocomplete="name" placeholder="Ej. Ana Torres Salgado" />
      <span class="field__error">${icon('i-alert', 13)} Escribe el nombre del asistente.</span>
    </label>
    <label class="field">
      <span>Correo electrónico</span>
      <input class="input" name="email" type="email" required autocomplete="email" placeholder="ana@ejemplo.com" />
      <span class="field__error">Escribe un correo válido (ej. ana@ejemplo.com).</span>
    </label>
    <div class="form__actions" style="margin-top:16px">
      <button type="button" class="btn btn--quiet" data-role="f:cancel">Cancelar</button>
      <button type="submit" class="btn btn--primary">${icon('i-check', 14)}&nbsp;Crear asistente</button>
    </div>
  `;
  return form;
}

export function initAsistentes(container) {
  container.innerHTML = TEMPLATE;

  const tbody = container.querySelector('[data-role="asistentes:tbody"]');
  const stateBox = container.querySelector('[data-role="asistentes:state"]');
  const tableWrap = container.querySelector('[data-role="asistentes:table-wrap"]');
  const countStamp = container.querySelector('[data-role="asistentes:count"]');

  container.querySelector('[data-role="asistentes:new"]').addEventListener('click', openForm);
  stateBox.addEventListener('click', (e) => {
    if (e.target.closest('[data-role="asistentes:empty-new"]')) openForm();
  });

  function openForm() {
    const form = buildForm();
    openModal('Nuevo asistente', form);
    form.querySelector('[data-role="f:cancel"]').addEventListener('click', closeModal);
    form.querySelector('[name="rut"]').focus();

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const rut = form.rut.value.trim();
      const nombreCompleto = form.nombre_completo.value.trim();
      const email = form.email.value.trim();
      const rutOk = /^\d{1,2}(\.\d{3}){1,2}-[\dkK]$|^\d{7,8}-[\dkK]$/i.test(rut);
      const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

      form.rut.closest('.field').classList.toggle('has-error', !rutOk);
      form.nombre_completo.closest('.field').classList.toggle('has-error', !nombreCompleto);
      form.email.closest('.field').classList.toggle('has-error', !emailOk);
      if (!rutOk || !nombreCompleto || !emailOk) return;

      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      try {
        await api.asistentes.create({ rut, nombre_completo: nombreCompleto, email });
        closeModal();
        toast(`${nombreCompleto} quedó registrado`);
        await refresh();
      } catch (err) {
        toast(err.message, 'error');
      } finally {
        submit.disabled = false;
      }
    });
  }

  tbody.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action="ver"]');
    if (btn) showDetail(btn.dataset.id);
  });

  async function showDetail(id) {
    try {
      const a = await api.asistentes.get(id);
      openModal(
        `Asistente ${shortId(a.asistente_id)}`,
        dlNode([
          ['ID', a.asistente_id],
          ['RUT', a.rut],
          ['Nombre', a.nombre_completo],
          ['Correo', a.email],
          ['Registrado', fmtDate(a.fecha_registro)],
        ]),
      );
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return iso;
    }
  }

  async function refresh() {
    stateBox.innerHTML = '';
    stateBox.classList.add('is-hidden');
    tableWrap.classList.remove('is-hidden');
    tbody.innerHTML = `
      <tr class="skeleton-row"><td><span class="skeleton" style="width:20%;display:block"></span></td>
      <td><span class="skeleton" style="width:55%;display:block"></span></td>
      <td><span class="skeleton" style="width:40%;display:block"></span></td>
      <td><span class="skeleton" style="width:70%;display:block"></span></td>
      <td><span class="skeleton" style="width:30%;display:block"></span></td></tr>
    `;
    try {
      const asistentes = await api.asistentes.list();
      if (!asistentes || asistentes.length === 0) {
        tableWrap.classList.add('is-hidden');
        stateBox.classList.remove('is-hidden');
        stateBox.innerHTML = EMPTY_HTML;
        countStamp.textContent = '';
        return;
      }
      countStamp.textContent = `${asistentes.length} en la lista`;
      tbody.innerHTML = asistentes
        .map(
          (a) => `
            <tr>
              <td class="id-cell" data-label="ID">${esc(shortId(a.asistente_id))}</td>
              <td data-label="Nombre">
                <span class="name-cell">
                  <span class="avatar" aria-hidden="true">${esc(initials(a.nombre_completo))}</span>
                  <span class="cell-strong">${esc(a.nombre_completo)}</span>
                </span>
              </td>
              <td data-label="RUT">${esc(a.rut)}</td>
              <td data-label="Correo">${esc(a.email)}</td>
              <td class="cell-actions">
                <div class="row-actions">
                  <button class="icon-btn" data-action="ver" data-id="${esc(a.asistente_id)}" type="button" title="Ver detalle" aria-label="Ver asistente ${esc(a.nombre_completo)}">${icon('i-eye', 16)}</button>
                </div>
              </td>
            </tr>
          `,
        )
        .join('');
    } catch (err) {
      tableWrap.classList.add('is-hidden');
      stateBox.classList.remove('is-hidden');
      stateBox.innerHTML = `
        <div class="empty">
          <span class="stamp stamp--reverted">sin conexión</span>
          <h3 class="empty__title">El registro no se pudo cargar</h3>
          <p class="empty__text">${esc(err.message)} Verifica el servicio de venta y reintenta.</p>
          <button class="btn" type="button" data-action="retry">Reintentar</button>
        </div>
      `;
      stateBox.querySelector('[data-action="retry"]').addEventListener('click', refresh);
    }
  }

  return { refresh };
}
