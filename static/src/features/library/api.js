import { apiGet, apiPost, query } from '../../api/client.js';

export async function fetchRecentPlays() {
    const { data } = await apiGet('/api/history');
    return data;
}

export async function fetchTopSongs(range) {
    const { data } = await apiGet(`/api/stats/top-songs${query({ range })}`);
    return data;
}

export async function fetchTopArtists(range) {
    const { data } = await apiGet(`/api/stats/top-artists${query({ range })}`);
    return data;
}

export async function syncSpotify() {
    const { data } = await apiPost('/api/refresh');
    return data;
}
