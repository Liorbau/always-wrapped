import { apiGet, query } from '../../api/client.js';

export async function searchLibrary(term, range) {
    const { data } = await apiGet(`/api/search${query({ q: term, range })}`);
    return data;
}
