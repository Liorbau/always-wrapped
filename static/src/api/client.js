// The only place that talks to the network. One set of headers, one JSON
// parse, one error shape — the server's envelope:
//   {"error": {"code": "...", "message": "...", "details": {}}}

export const NETWORK_ERROR = 'NETWORK_ERROR';
export const MALFORMED_RESPONSE = 'MALFORMED_RESPONSE';

export class ApiError extends Error {
    constructor({ code, message, details }, status) {
        super(message || 'Something went wrong.');
        this.name = 'ApiError';
        this.code = code || 'INTERNAL_ERROR';
        this.details = details || {};
        this.status = status;
    }
}

async function request(path, { method = 'GET', body } = {}) {
    let response;
    try {
        response = await fetch(path, {
            method,
            credentials: 'same-origin',
            headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    } catch {
        throw new ApiError(
            { code: NETWORK_ERROR, message: 'Network error — is the server up?' }, 0);
    }

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
        throw new ApiError((payload && payload.error) || {}, response.status);
    }
    if (payload === null) {
        throw new ApiError(
            { code: MALFORMED_RESPONSE, message: 'The server sent something unreadable.' },
            response.status);
    }
    return { status: response.status, data: payload };
}

export function apiGet(path) {
    return request(path);
}

export function apiPost(path, body = {}) {
    return request(path, { method: 'POST', body });
}

export function query(params) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null && value !== '') search.set(key, value);
    }
    const encoded = search.toString();
    return encoded ? `?${encoded}` : '';
}
