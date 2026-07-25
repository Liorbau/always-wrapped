import { apiGet, query } from '../../api/client.js';

export async function fetchEdition({ period = 'week', force = false, start, end }) {
    const { data } = await apiGet(`/api/wrapped${query({
        period,
        force: force ? '1' : '',
        start: period === 'custom' ? start : '',
        end: period === 'custom' ? end : '',
    })}`);
    return data;
}
