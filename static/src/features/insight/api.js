import { apiGet, query } from '../../api/client.js';
import { browserTimezone } from '../../shared/timezone.js';

export async function fetchInsight() {
    const { data } = await apiGet(`/api/insight${query({ tz: browserTimezone() })}`);
    return data;
}
