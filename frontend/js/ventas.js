import { api } from './api.js';
import { esc, toast, openModal, dlNode } from './ui.js';

const TEMPLATE = `
  <div class="view-header">
    <h2>Ventas</h2>
    <button class="btn btn--primary" data-role="ventas:new">Vender entrada</button>
  </div>
  <form class="card form is-hidden" data-role="ventas:form">
    <div class="form__grid">
      <label>
        Evento
        <select name="evento" data-role="ventas:evento" required>
          <option value="">Selecciona un evento</option>
        </select>
      </label>
      <label>
        Sección
        <select name="seccion" data-role="ventas:seccion" required disabled>
          <option value="">Primero elige un evento</option>
        </select>
      </label>
      <label>
        Asistente
        <select name="asistente" data-role="ventas:asistente" required>
          <option value="">Cargando…</option>
        </select>
      </label>
      <label>
        Cantidad
        <input name="cantidad" type="number" min="1" step="1" value="1" required />
      </label>
    </div>
    <p class="aviso" data-role="ventas:disponibilidad">La disponibilidad se valida contra el sistema de Aforo.</p>
    <div class="form__actions">
      <button type="button" class="btn" data-role="ventas:form-cancel">Cancelar</button>
      <button type="submit" class="btn btn--primary" data-role="ventas:submit">Vender</button>
    </div>
  </form>
  <div class="card">
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Asistente</th>
          <th>Evento</th>
          <th>Sección</th>
          <th>Cant.</th>
          <th>Estado</th>
          <th></th>
        </tr>
      </thead>
      <tbody data-role="ventas:tbody"></tbody>
    </table>
  </div>
`;

function q(container, role) {
  return container.querySelector(`[data-role="${role}"]`);
}

function asistenteLabel(v) {
  if (v.asistente && typeof v.asistente === 'object') return v.asistente.nombre ?? `#${v.asistente.id}`;
  return v.asistente_nombre ?? `#${v.asistente_id ?? '?'}`;
}

function eventoLabel(v) {
  if (v.evento && typeof v.evento === 'object') return v.evento.nombre ?? `#${v.evento.id}`;
  return v.evento_nombre ?? `#${v.evento_id ?? '?'}`;
}

function seccionLabel(v) {
  if (v.seccion && typeof v.seccion === 'object') return v.seccion.nombre ?? `#${v.seccion.id}`;
  return v.seccion_nombre ?? `#${v.seccion_id ?? '?'}`;
}

function estadoOf(v) {
  return v.estado ?? 'vendido';
}

export function initVentas(container) {
  container.innerHTML = TEMPLATE;

  const form = q(container, 'ventas:form');
  const tbody = q(container, 'ventas:tbody');
  const eventoSel = q(container, 'ventas:evento');
  const seccionSel = q(container, 'ventas:seccion');
  const asistenteSel = q(container, 'ventas:asistente');
  const disponibilidad = q(container, 'ventas:disponibilidad');
  const submitBtn = q(container, 'ventas:submit');

  async function cargarAsistentes() {
    try {
      const asistentes = await api.asistentes.list();
      asistenteSel.innerHTML =
        '<option value="">Selecciona un asistente</option>' +
        (asistentes || [])
          .map((a) => `<option value="${esc(a.id)}">${esc(a.nombre)} — ${esc(a.email)}</option>`)
          .join('');
      asistenteSel.disabled = !asistentes || asistentes.length === 0;
    } catch (err) {
      asistenteSel.innerHTML = '<option value="">No se pudo cargar</option>';
      toast(err.message, 'error');
    }
  }

  async function cargarEventos() {
    eventoSel.innerHTML = '<option value="">Cargando…</option>';
    try {
      const eventos = await api.catalogo.eventos();
      eventoSel.innerHTML =
        '<option value="">Selecciona un evento</option>' +
        (eventos || [])
          .map((e) => `<option value="${esc(e.id)}">${esc(e.nombre)}</option>`)
          .join('');
      seccionSel.innerHTML = '<option value="">Primero elige un evento</option>';
      seccionSel.disabled = true;
      disponibilidad.textContent = 'La disponibilidad se valida contra el sistema de Aforo.';
    } catch (err) {
      eventoSel.innerHTML = '<option value="">No se pudo cargar</option>';
      toast(err.message, 'error');
    }
  }

  async function cargarSecciones(eventoId) {
    seccionSel.innerHTML = '<option value="">Cargando…</option>';
    seccionSel.disabled = true;
    disponibilidad.textContent = 'Cargando secciones…';
    try {
      const secciones = await api.catalogo.secciones(eventoId);
      if (!secciones || secciones.length === 0) {
        seccionSel.innerHTML = '<option value="">Sin secciones</option>';
        disponibilidad.textContent = 'Este evento no tiene secciones definidas.';
        return;
      }
      seccionSel.innerHTML =
        '<option value="">Selecciona una sección</option>' +
        secciones
          .map(
            (s) =>
              `<option value="${esc(s.id)}">${esc(s.nombre)} — ${esc(s.disponibles ?? '?')}/${esc(s.total ?? '?')} disponibles</option>`,
          )
          .join('');
      seccionSel.disabled = false;
      const total = secciones.reduce((acc, s) => acc + (Number(s.disponibles) || 0), 0);
      disponibilidad.textContent = `${secciones.length} sección(es), ${total} entradas disponibles en total.`;
      mostrarDisponibilidad();
    } catch (err) {
      seccionSel.innerHTML = '<option value="">No se pudo cargar</option>';
      disponibilidad.textContent = 'No se pudo consultar la disponibilidad de Aforo.';
      toast(err.message, 'error');
    }
  }

  function mostrarDisponibilidad() {
    const opt = seccionSel.options[seccionSel.selectedIndex];
    if (opt) disponibilidad.textContent = opt.textContent;
  }

  q(container, 'ventas:new').addEventListener('click', async () => {
    form.classList.remove('is-hidden');
    await Promise.all([cargarEventos(), cargarAsistentes()]);
  });

  q(container, 'ventas:form-cancel').addEventListener('click', () => {
    form.classList.add('is-hidden');
    form.reset();
    seccionSel.disabled = true;
  });

  eventoSel.addEventListener('change', () => {
    const id = Number(eventoSel.value);
    if (!id) {
      seccionSel.innerHTML = '<option value="">Primero elige un evento</option>';
      seccionSel.disabled = true;
      return;
    }
    cargarSecciones(id);
  });

  seccionSel.addEventListener('change', mostrarDisponibilidad);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    const payload = {
      asistente_id: Number(form.asistente.value),
      evento_id: Number(form.evento.value),
      seccion_id: Number(form.seccion.value),
      cantidad: Number(form.cantidad.value),
    };
    if (!payload.evento_id || !payload.seccion_id || !payload.asistente_id) {
      toast('Complete todos los campos de la venta.', 'error');
      submitBtn.disabled = false;
      return;
    }
    try {
      await api.ventas.create(payload);
      form.classList.add('is-hidden');
      form.reset();
      seccionSel.disabled = true;
      toast('Entrada vendida correctamente');
      await Promise.all([refresh(), cargarEventos()]);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      submitBtn.disabled = false;
    }
  });

  tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const { id, action } = btn.dataset;
    if (action === 'ver') {
      try {
        const v = await api.ventas.get(Number(id));
        openModal(
          `Venta #${v.id}`,
          dlNode([
            ['ID', v.id],
            ['Asistente', asistenteLabel(v)],
            ['Evento', eventoLabel(v)],
            ['Sección', seccionLabel(v)],
            ['Cantidad', v.cantidad],
            ['Estado', estadoOf(v)],
            ['Creado', v.created_at ?? '—'],
          ]),
        );
      } catch (err) {
        toast(err.message, 'error');
      }
      return;
    }
    if (action === 'revertir') {
      if (!confirm('¿Revertir esta venta? Se devolverá la entrada a Aforo.')) return;
      try {
        await api.ventas.revert(Number(id));
        toast('Venta revertida');
        await Promise.all([refresh(), cargarEventos()]);
      } catch (err) {
        toast(err.message, 'error');
      }
    }
  });

  async function refresh() {
    tbody.innerHTML = '<tr><td class="table__empty" colspan="7">Cargando…</td></tr>';
    try {
      const ventas = await api.ventas.list();
      if (!ventas || ventas.length === 0) {
        tbody.innerHTML = '<tr><td class="table__empty" colspan="7">No hay ventas registradas.</td></tr>';
        return;
      }
      tbody.innerHTML = ventas
        .map(
          (v) => `
            <tr>
              <td>${esc(v.id)}</td>
              <td>${esc(asistenteLabel(v))}</td>
              <td>${esc(eventoLabel(v))}</td>
              <td>${esc(seccionLabel(v))}</td>
              <td>${esc(v.cantidad)}</td>
              <td><span class="badge">${esc(estadoOf(v))}</span></td>
              <td>
                <div class="table__actions">
                  <button class="btn btn--small" data-action="ver" data-id="${esc(v.id)}">Ver</button>
                  <button class="btn btn--small btn--danger" data-action="revertir" data-id="${esc(v.id)}">Revertir</button>
                </div>
              </td>
            </tr>
          `,
        )
        .join('');
    } catch (err) {
      tbody.innerHTML = '<tr><td class="table__empty" colspan="7">No se pudo cargar la lista de ventas.</td></tr>';
      toast(err.message, 'error');
    }
  }

  return { refresh };
}