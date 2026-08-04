import { apiGet, apiPost } from '../../api/client.js';

export async function fetchPlaylists() {
    const { data } = await apiGet('/api/agent/playlists?limit=100');
    return data;
}

export async function saveFeedback(playlistId, body) {
    const { data } = await apiPost(`/api/agent/playlists/${playlistId}/feedback`, body);
    return data;
}

export async function unlock(token) {
    const { data } = await apiPost('/api/owner/unlock', { token });
    return data;
}

export async function unlockStatus() {
    const { data } = await apiGet('/api/owner/status');
    return data;
}
