import { api } from './api.js';
import { esc, toast, openModal, dlNode } from './ui.js';

const TEMPLATE = `
  <div class="view-header">
    <h2>Asistentes</h2>
    <button class="btn btn--primary" data-role="asistentes:new">Nuevo asistente</button>
  </div>
  <form class="card form is-hidden" data-role="asistentes:form">
    <div class="form__grid">
      <label>
        Nombre
        <input name="nombre" required autocomplete="off" />
      </label>
      <label>
        Email
        <input name="email" type="email" required autocomplete="off" />
      </label>
    </div>
    <div class="form__actions">
      <button type="button" class="btn" data-role="asistentes:form-cancel">Cancelar</button>
      <button type="submit" class="btn btn--primary">Crear asistente</button>
    </div>
  </form>
  <div class="card">
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Nombre</th>
          <th>Email</th>
          <th></th>
        </tr>
      </thead>
      <tbody data-role="asistentes:tbody"></tbody>
    </table>
  </div>
`;

export function initAsistentes(container) {
  container.innerHTML = TEMPLATE;

  const form = container.querySelector('[data-role="asistentes:form"]');
  const tbody = container.querySelector('[data-role="asistentes:tbody"]');

  container.querySelector('[data-role="asistentes:new"]').addEventListener('click', () => {
    form.classList.remove('is-hidden');
    form.querySelector('[name="nombre"]').focus();
  });

  container
    .querySelector('[data-role="asistentes:form-cancel"]')
    .addEventListener('click', () => {
      form.classList.add('is-hidden');
      form.reset();
    });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(form));
    try {
      await api.asistentes.create(payload);
      form.classList.add('is-hidden');
      form.reset();
      toast('Asistente creado correctamente');
      await refresh();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  tbody.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const { id, action } = btn.dataset;
    if (action === 'ver') showDetail(Number(id));
  });

  async function showDetail(id) {
    try {
      const a = await api.asistentes.get(id);
      openModal(
        `Asistente #${a.id}`,
        dlNode([
          ['ID', a.id],
          ['Nombre', a.nombre],
          ['Email', a.email],
          ['Creado', a.created_at ?? '—'],
        ]),
      );
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function refresh() {
    tbody.innerHTML = '<tr><td class="table__empty" colspan="4">Cargando…</td></tr>';
    try {
      const asistentes = await api.asistentes.list();
      if (!asistentes || asistentes.length === 0) {
        tbody.innerHTML = '<tr><td class="table__empty" colspan="4">No hay asistentes registrados.</td></tr>';
        return;
      }
      tbody.innerHTML = asistentes
        .map(
          (a) => `
            <tr>
              <td>${esc(a.id)}</td>
              <td>${esc(a.nombre)}</td>
              <td>${esc(a.email)}</td>
              <td>
                <div class="table__actions">
                  <button class="btn btn--small" data-action="ver" data-id="${esc(a.id)}">Ver</button>
                </div>
              </td>
            </tr>
          `,
        )
        .join('');
    } catch (err) {
      tbody.innerHTML = '<tr><td class="table__empty" colspan="4">No se pudo cargar la lista de asistentes.</td></tr>';
      toast(err.message, 'error');
    }
  }

  return { refresh };
}