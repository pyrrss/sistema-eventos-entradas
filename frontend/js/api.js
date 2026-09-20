const API_BASE = 'http://localhost:8002';

export class APIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

async function request(path, options = {}) {
    let res;
    try {
        res = await fetch(`${API_BASE}${path}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
    } catch {
        throw new APIError('No se pudo conectar con el servidor. Verifique que esté en línea.', 0, null);
    }

    let data = null;
    const text = await res.text();
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = null;
        }
    }

    if (!res.ok) {
        const detail = (data && (data.detail || data.message)) || `Error ${res.status}`;
        throw new APIError(typeof detail === 'string' ? detail : JSON.stringify(detail), res.status, data);
    }

    return data;
}

export const api = {
    health: () => request('/api/health'),
    asistentes: {
        list: () => request('/api/asistentes'),
        get: (id) => request(`/api/asistentes/${id}`),
        create: (payload) => request('/api/asistentes', { method: 'POST', body: JSON.stringify(payload) }),
    },
    ventas: {
        list: () => request('/api/ventas'),
        get: (id) => request(`/api/ventas/${id}`),
        create: (payload) => request('/api/ventas', { method: 'POST', body: JSON.stringify(payload) }),
        revert: (id) => request(`/api/ventas/${id}`, { method: 'DELETE' }),
    },
    catalogo: {
        eventos: () => request('/api/eventos'),
        secciones: (eventoId) => request(`/api/eventos/${eventoId}/secciones`),
    },
};
