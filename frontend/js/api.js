const API_BASE = 'http://localhost:8002/api/v1';
const API_KEY = 'dev-key-123';

export class APIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

async function request(path, options = {}) {
    const { headers, ...rest } = options;
    let res;
    try {
        res = await fetch(`${API_BASE}${path}`, {
            ...rest,
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY,
                ...(headers || {}),
            },
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
    health: () => request('/health'),
    asistentes: {
        list: () => request('/asistentes'),
        get: (id) => request(`/asistentes/${id}`),
        create: (payload) => request('/asistentes', { method: 'POST', body: JSON.stringify(payload) }),
        update: (id, payload) => request(`/asistentes/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
    },
    ventas: {
        list: () => request('/ventas'),
        get: (id) => request(`/ventas/${id}`),
        create: (payload, idempotencyKey) => request('/ventas', {
            method: 'POST',
            headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
            body: JSON.stringify(payload),
        }),
        revert: (id) => request(`/ventas/${id}`, { method: 'DELETE' }),
    },
    catalogo: {
        eventos: () => request('/eventos'),
        secciones: (eventoId) => request(`/eventos/${eventoId}/secciones`),
    },
};