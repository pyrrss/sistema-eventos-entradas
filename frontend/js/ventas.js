import { api } from './api.js';
import { esc, toast, openModal, closeModal, confirmDialog, dlNode, icon } from './ui.js';

const TEMPLATE = `
  <div class="view-head">
    <div class="view-head__titles">
      <h2>Ventas</h2>
      <span class="count-stamp" data-role="ventas:count"></span>
    </div>
    <div class="view-head__actions">
      <button class="btn btn--primary" data-role="ventas:new" type="button">
        ${icon('i-plus', 14)} Vender entrada
      </button>
    </div>
  </div>

  <div class="card">
    <div class="card__band">
      <span class="card__band-title">${icon('i-ticket', 15)} Libro de ventas</span>
      <span class="station__hint">La disponibilidad se sincroniza con el servicio de Aforo</span>
    </div>
    <div class="perfo"></div>
    <div data-role="ventas:state"></div>
    <div class="table-wrap" data-role="ventas:table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">Folio</th>
            <th scope="col">Asistente</th>
            <th scope="col">Evento</th>
            <th scope="col">Sección</th>
            <th scope="col" class="num">Cant.</th>
            <th scope="col">Estado</th>
            <th scope="col"><span class="sr-label">Acciones</span></th>
          </tr>
        </thead>
        <tbody data-role="ventas:tbody"></tbody>
      </table>
    </div>
  </div>
`;

const EMPTY_HTML = `
  <div class="empty">
    <svg class="empty__art" width="56" height="56" viewBox="0 0 24 24" aria-hidden="true">
      <use href="#i-ticket" />
    </svg>
    <h3 class="empty__title">Aún no hay ventas en el libro</h3>
    <p class="empty__text">Cuando vendas tu primera entrada aparecerá aquí, con su estado sincronizado contra Aforo.</p>
    <button class="btn btn--primary" data-role="ventas:empty-new" type="button">${'Vender entrada'}</button>
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
  const e = String(v.estado ?? '').toUpperCase();
  if (e === 'VENDIDA') return 'vendido';
  if (e === 'ANULADA') return 'revertido';
  return 'otro';
}

function stampFor(estado) {
  const e = String(estado).toLowerCase();
  const cls = e === 'vendido' ? 'stamp--valid' : e === 'revertido' ? 'stamp--reverted' : 'stamp--neutral';
  return `<span class="stamp ${cls}">${esc(e)}</span>`;
}

function skeletonRows(cols) {
  const widths = ['18%', '30%', '24%', '20%', '10%', '16%', '24%'];
  return Array.from({ length: 5 }, () => {
    const tds = widths
      .slice(0, cols)
      .map((w) => `<td class="skeleton-cell"><span class="skeleton" style="width:${w};display:block"></span></td>`)
      .join('');
    return `<tr class="skeleton-row">${tds}</tr>`;
  }).join('');
}

function plural(n, sing, plur) {
  return `${n} ${Number(n) === 1 ? sing : plur}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

/* ---------- Ventanilla de venta (modal por estaciones) ---------- */

function buildSaleModal() {
  const root = document.createElement('form');
  root.className = 'sale';
  root.noValidate = true;
  root.innerHTML = `
    <div class="station" data-station="evento">
      <span class="station__num" aria-hidden="true">1</span>
      <div style="min-width:0">
        <div class="station__head">
          <span class="station__title">Evento</span>
        </div>
        <label class="field">
          <select class="select" data-role="m:evento" required aria-label="Evento">
            <option value="">Cargando eventos…</option>
          </select>
        </label>
      </div>
    </div>

    <div class="station station--locked" data-station="seccion">
      <span class="station__num" aria-hidden="true">2</span>
      <div style="min-width:0">
        <div class="station__head">
          <span class="station__title">Sección</span>
          <span class="station__hint" data-role="m:seccion-hint">Elige primero un evento</span>
        </div>
        <div class="sector-pick" data-role="m:sectores" role="radiogroup" aria-label="Secciones del evento">
          <p class="station__hint" data-role="m:sectores-empty">Cargando secciones…</p>
        </div>
      </div>
    </div>

    <div class="station" data-station="asistente">
      <span class="station__num" aria-hidden="true">3</span>
      <div style="min-width:0">
        <div class="station__head">
          <span class="station__title">Asistente</span>
        </div>
        <label class="field">
          <select class="select" data-role="m:asistente" required aria-label="Asistente">
            <option value="">Cargando asistentes…</option>
          </select>
        </label>
      </div>
    </div>

    <div class="station" data-station="cantidad">
      <span class="station__num" aria-hidden="true">4</span>
      <div style="min-width:0">
        <div class="station__head">
          <span class="station__title">Cantidad</span>
          <span class="station__hint" data-role="m:cup_max"></span>
        </div>
        <div class="stepper">
          <button type="button" data-role="m:minus" aria-label="Quitar una entrada">&minus;</button>
          <output data-role="m:qty" aria-live="polite">1</output>
          <button type="button" data-role="m:plus" aria-label="Agregar una entrada">+</button>
        </div>
      </div>
    </div>

    <div class="stub-total" aria-hidden="true">
      <div>
        <div class="stub-total__label">Se venderá</div>
        <div data-role="m:summary" class="cell-sub" style="font-weight:600;color:var(--ink)">Completa las estaciones</div>
      </div>
      <div class="stub-total__value" data-role="m:total">1</div>
    </div>
    <p class="field__error" data-role="m:error" role="alert"></p>
    <div class="form__actions" style="margin-top:10px">
      <button type="button" class="btn btn--quiet" data-role="m:cancel">Cancelar</button>
      <button type="submit" class="btn btn--primary" data-role="m:submit" disabled>${icon('i-ticket', 14)}&nbsp;Vender entrada</button>
    </div>
  `;
  return root;
}

export function initVentas(container) {
  container.innerHTML = TEMPLATE;

  const tbody = q(container, 'ventas:tbody');
  const stateBox = q(container, 'ventas:state');
  const tableWrap = q(container, 'ventas:table-wrap');
  const countStamp = q(container, 'ventas:count');
  let lastVentas = [];

  q(container, 'ventas:new').addEventListener('click', openSale);
  stateBox.addEventListener('click', (e) => {
    if (e.target.closest('[data-role="ventas:empty-new"]')) openSale();
  });

  async function openSale() {
    const modal = buildSaleModal();
    openModal('Ventanilla de venta', modal);

    const eventoSel = modal.querySelector('[data-role="m:evento"]');
    const asistenteSel = modal.querySelector('[data-role="m:asistente"]');
    const sectores = modal.querySelector('[data-role="m:sectores"]');
    const sectoresEmpty = modal.querySelector('[data-role="m:sectores-empty"]');
    const seccionHint = modal.querySelector('[data-role="m:seccion-hint"]');
    const stationSeccion = modal.querySelector('[data-station="seccion"]');
    const qtyOut = modal.querySelector('[data-role="m:qty"]');
    const cupMax = modal.querySelector('[data-role="m:cup_max"]');
    const summary = modal.querySelector('[data-role="m:summary"]');
    const totalOut = modal.querySelector('[data-role="m:total"]');
    const errEl = modal.querySelector('[data-role="m:error"]');
    const submitBtn = modal.querySelector('[data-role="m:submit"]');

    let secciones = [];
    let seleccion = null;
    let qty = 1;
    // Clave por INTENTO (una por modal abierto): si el submit falla por red
    // y el usuario reintenta desde esta misma ventana, el servidor reconoce
    // el duplicado y devuelve la venta original en vez de crear otra.
    const idempotencyKey = crypto.randomUUID();

    modal.querySelector('[data-role="m:cancel"]').addEventListener('click', closeModal);

    Promise.all([cargarEventos(), cargarAsistentes()]);

    async function cargarEventos() {
      try {
        const eventos = await api.catalogo.eventos();
        eventoSel.innerHTML =
          '<option value="">Selecciona un evento</option>' +
          (eventos || []).map((e) => `<option value="${esc(e.id)}">${esc(e.nombre)}</option>`).join('');
        if (!eventos || eventos.length === 0) {
          eventoSel.innerHTML = '<option value="">No hay eventos en Aforo</option>';
        }
      } catch (err) {
        eventoSel.innerHTML = '<option value="">No se pudo consultar Aforo</option>';
        showError(err.message);
      }
    }

    async function cargarAsistentes() {
      try {
        const asistentes = await api.asistentes.list();
        asistenteSel.innerHTML =
          '<option value="">Selecciona un asistente</option>' +
          (asistentes || [])
            .map((a) => `<option value="${esc(a.asistente_id)}">${esc(a.nombre_completo)} · ${esc(a.email)}</option>`)
            .join('');
        if (!asistentes || asistentes.length === 0) {
          asistenteSel.innerHTML = '<option value="">Primero registra un asistente</option>';
        }
      } catch (err) {
        asistenteSel.innerHTML = '<option value="">No se pudo cargar</option>';
      }
    }

    eventoSel.addEventListener('change', async () => {
      seleccion = null;
      const id = eventoSel.value;
      sectores.innerHTML = '';
      if (!id) {
        stationSeccion.classList.add('station--locked');
        seccionHint.textContent = 'Elige primero un evento';
        renderSummary();
        return;
      }
      seccionHint.textContent = 'Consultando aforo…';
      sectores.innerHTML = '<p class="station__hint">Cargando secciones…</p>';
      try {
        secciones = (await api.catalogo.secciones(id)) || [];
        renderSectores();
      } catch (err) {
        secciones = [];
        sectores.innerHTML = '';
        sectores.appendChild(sectorasErrorNode(err.message));
        seccionHint.textContent = 'Aforo no responde';
      }
      renderSummary();
    });

    function sectorasErrorNode(msg) {
      const p = document.createElement('p');
      p.className = 'field__error';
      p.style.display = 'flex';
      p.textContent = msg;
      return p;
    }

    function renderSectores() {
      sectores.innerHTML = '';
      if (secciones.length === 0) {
        seccionHint.textContent = 'Este evento no tiene secciones';
        const p = document.createElement('p');
        p.className = 'station__hint';
        p.textContent = 'Aforo no tiene secciones registradas para este evento.';
        sectores.appendChild(p);
        return;
      }
      const disponibles = secciones.reduce((n, s) => n + (Number(s.disponibles) || 0), 0);
      seccionHint.textContent = `${disponibles} lugares libres en ${plural(secciones.length, 'sección', 'secciones')}`;

      const nodes = [];
      for (const s of secciones) {
        const total = Number(s.total) || 0;
        const disp = Number(s.disponibles) || 0;
        const lleno = disp <= 0;
        const pctOcupado = total > 0 ? Math.round(((total - disp) / total) * 100) : 0;

        const opt = document.createElement('div');
        opt.className = `sector${lleno ? ' is-full' : ''}`;
        opt.setAttribute('role', 'radio');
        opt.setAttribute('aria-checked', 'false');
        opt.tabIndex = -1;
        if (lleno) opt.setAttribute('aria-disabled', 'true');
        opt.setAttribute('aria-label', `${s.nombre}: ${disp} de ${total} lugares libres, ${pctOcupado}% del aforo ocupado`);
        opt.dataset.id = s.id;
        opt.innerHTML = `
          <div class="sector__row">
            <span class="sector__name">${esc(s.nombre)}</span>
            <span class="sector__count">${disp}/${total} libres</span>
          </div>
          <div class="sector__meter">
            <div class="meter" role="img" aria-label="${pctOcupado}% del aforo ocupado" title="${pctOcupado}% del aforo ocupado">
              <div class="meter__fill${pctOcupado >= 90 ? ' is-nearly-full' : ''}" style="--p:${(pctOcupado / 100).toFixed(3)}"></div>
            </div>
            <span class="sector__pct">${pctOcupado}% ocupado</span>
          </div>
        `;
        const pick = () => {
          seleccion = s;
          for (const n of nodes) {
            const on = n.el === opt;
            n.el.classList.toggle('is-selected', on);
            n.el.setAttribute('aria-checked', on ? 'true' : 'false');
            n.el.tabIndex = on ? 0 : -1;
          }
          opt.tabIndex = 0;
          stationSeccion.classList.remove('station--locked');
          clampQty();
          renderSummary();
        };
        if (!lleno) {
          opt.addEventListener('click', pick);
          opt.addEventListener('keydown', (e) => {
            const dir = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
            if (dir) {
              e.preventDefault();
              const libres = nodes.filter((n) => !n.lleno);
              const at = libres.findIndex((n) => n.el === opt);
              const next = libres[(at + dir + libres.length) % libres.length];
              if (next) {
                next.el.click();
                next.el.focus();
              }
            } else if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              pick();
            }
          });
        }
        nodes.push({ el: opt, lleno });
        sectores.appendChild(opt);
      }
      const firstLibre = nodes.find((n) => !n.lleno);
      if (firstLibre && !seleccion) firstLibre.el.tabIndex = 0;
      sectoresEmpty.remove();
    }

    modal.querySelector('[data-role="m:minus"]').addEventListener('click', () => {
      qty = Math.max(1, qty - 1);
      renderQty();
    });
    modal.querySelector('[data-role="m:plus"]').addEventListener('click', () => {
      qty = Math.min(cantidadMax(), qty + 1);
      renderQty();
    });
    asistenteSel.addEventListener('change', renderSummary);

    function cantidadMax() {
      return Math.max(1, Number(seleccion?.disponibles) || 1);
    }

    function clampQty() {
      qty = Math.min(Math.max(1, qty), cantidadMax());
      renderQty();
    }

    function renderQty() {
      qtyOut.textContent = qty;
      totalOut.textContent = qty;
      const max = seleccion ? Number(seleccion.disponibles) : null;
      cupMax.textContent = max != null ? `Máximo ${max} según Aforo` : '';
      modal.querySelector('[data-role="m:plus"]').disabled = max != null && qty >= max;
      modal.querySelector('[data-role="m:minus"]').disabled = qty <= 1;
      renderSummary();
    }

    function renderSummary() {
      const partes = [];
      if (eventoSel.selectedOptions[0]?.value) partes.push(eventoSel.selectedOptions[0].textContent);
      if (seleccion) partes.push(`Sección ${seleccion.nombre}`);
      if (asistenteSel.value && asistenteSel.selectedOptions[0]) {
        partes.push(asistenteSel.selectedOptions[0].textContent.split(' · ')[0]);
      }
      summary.textContent = partes.length ? partes.join(' — ') : 'Completa las estaciones';
      const listo = eventoSel.value && seleccion && asistenteSel.value && qty >= 1;
      submitBtn.disabled = !listo;
      if (listo) showError('');
    }

    function showError(msg) {
      errEl.textContent = msg;
      errEl.style.display = msg ? 'flex' : 'none';
    }

    modal.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (submitBtn.disabled) return;
      submitBtn.disabled = true;
      submitBtn.classList.add('is-loading');
      try {
        const creado = await api.ventas.create({
          asistente_id: asistenteSel.value,
          id_seccion_aforo: seleccion.id,
          nombre_evento: eventoSel.selectedOptions[0].textContent,
          nombre_seccion: seleccion.nombre,
          cantidad: qty,
        }, idempotencyKey);
        closeModal();
        toast(`${plural(qty, 'Entrada vendida', 'Entradas vendidas')} — ${qty} × ${seleccion.nombre}`);
        await refresh(creado?.id);
      } catch (err) {
        showError(err.message);
        toast(err.message, 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('is-loading');
      }
    });

    renderQty();
  }

  tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const { id, action } = btn.dataset;
    if (action === 'ver') {
      try {
        const v = await api.ventas.get(id);
        const node = document.createElement('div');
        node.appendChild(
          dlNode([
            ['Folio', `#${v.id}`],
            ['Asistente', asistenteLabel(v)],
            ['Evento', eventoLabel(v)],
            ['Sección', seccionLabel(v)],
            ['Cantidad', v.cantidad],
            ['Creado', fmtDate(v.created_at)],
          ]),
        );
        const stamp = document.createElement('p');
        stamp.style.marginTop = '14px';
        stamp.innerHTML = stampFor(estadoOf(v));
        node.appendChild(stamp);
        openModal(`Venta #${v.id}`, node);
      } catch (err) {
        toast(err.message, 'error');
      }
      return;
    }
    if (action === 'revertir') {
      const venta = lastVentas.find((v) => String(v.id) === String(id));
      const ok = await confirmDialog({
        title: 'Revertir venta',
        message: `Se devolverán ${
          venta ? plural(venta.cantidad, 'entrada', 'entradas') : 'las entradas'
        } de ${venta ? asistenteLabel(venta) : `#${id}`} al sistema de Aforo. Esta acción queda registrada.`,
        confirmText: 'Revertir venta',
      });
      if (!ok) return;
      try {
        await api.ventas.revert(id);
        toast('Venta revertida — el aforo se liberó');
        await refresh();
      } catch (err) {
        toast(err.message, 'error');
      }
    }
  });

  async function refresh(highlightId) {
    stateBox.innerHTML = '';
    stateBox.classList.add('is-hidden');
    tableWrap.classList.remove('is-hidden');
    tbody.innerHTML = skeletonRows(7);
    countStamp.textContent = '';
    try {
      const ventas = await api.ventas.list();
      lastVentas = ventas || [];
      if (lastVentas.length === 0) {
        tableWrap.classList.add('is-hidden');
        stateBox.classList.remove('is-hidden');
        stateBox.innerHTML = EMPTY_HTML;
        countStamp.textContent = 'El libro está vacío';
        return;
      }
      const activas = lastVentas.filter((v) => String(estadoOf(v)) === 'vendido').length;
      countStamp.textContent = `${plural(activas, 'entrada vendida', 'entradas vendidas')} · ${plural(lastVentas.length, 'folio', 'folios')}`;
      const fresh = highlightId == null ? null : String(highlightId);
      tbody.innerHTML = lastVentas
        .map((v) => {
          const estado = String(estadoOf(v)).toLowerCase();
          const revertible = estado === 'vendido';
          return `
            <tr${fresh && String(v.id) === fresh ? ' class="is-fresh"' : ''}>
              <td class="id-cell" data-label="Folio">#${esc(v.id)}</td>
              <td data-label="Asistente"><span class="cell-strong">${esc(asistenteLabel(v))}</span></td>
              <td data-label="Evento">${esc(eventoLabel(v))}</td>
              <td data-label="Sección">${esc(seccionLabel(v))}</td>
              <td class="num" data-label="Cantidad">${esc(v.cantidad)}</td>
              <td data-label="Estado">${stampFor(estado)}</td>
              <td class="cell-actions">
                <div class="row-actions">
                  <button class="icon-btn" data-action="ver" data-id="${esc(v.id)}" type="button" title="Ver detalle" aria-label="Ver venta ${esc(v.id)}">${icon('i-eye', 16)}</button>
                  ${
                    revertible
                      ? `<span class="btn-danger-zone"><button class="icon-btn icon-btn--danger" data-action="revertir" data-id="${esc(v.id)}" type="button" title="Revertir venta" aria-label="Revertir venta ${esc(v.id)}">${icon('i-undo', 16)}</button></span>`
                      : ''
                  }
                </div>
              </td>
            </tr>
          `;
        })
        .join('');
    } catch (err) {
      tableWrap.classList.add('is-hidden');
      stateBox.classList.remove('is-hidden');
      stateBox.innerHTML = `
        <div class="empty">
          <span class="stamp stamp--reverted">sin conexión</span>
          <h3 class="empty__title">El libro no se pudo abrir</h3>
          <p class="empty__text">${esc(err.message)} Verifica que los contenedores estén levantados (<code>docker compose up -d</code>) y reintenta.</p>
          <button class="btn" type="button" data-action="retry">Reintentar</button>
        </div>
      `;
      stateBox.querySelector('[data-action="retry"]').addEventListener('click', () => refresh());
    }
  }

  return { refresh };
}
