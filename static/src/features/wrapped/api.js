import { apiGet, query } from '../../api/client.js';
import { browserTimezone } from '../../shared/timezone.js';

export async function fetchEdition({ period = 'week', force = false, start, end }) {
    const { data } = await apiGet(`/api/wrapped${query({
        period,
        force: force ? '1' : '',
        start: period === 'custom' ? start : '',
        end: period === 'custom' ? end : '',
        tz: browserTimezone(),
    })}`);
    return data;
}
