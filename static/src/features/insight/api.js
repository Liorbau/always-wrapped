import { apiGet } from '../../api/client.js';

export async function fetchInsight() {
    const { data } = await apiGet('/api/insight');
    return data;
}
