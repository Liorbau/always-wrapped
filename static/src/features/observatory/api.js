import { apiGet, apiPost } from '../../api/client.js';

export async function fetchActivity() {
    const { data } = await apiGet('/api/agent/activity');
    return data;
}

export function triggerEvaluator() {
    return apiPost('/api/agent/evaluate');
}
