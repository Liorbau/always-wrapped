import { apiGet, apiPost, apiPut } from '../../api/client.js';

export async function unlock(token) {
    const { data } = await apiPost('/api/owner/unlock', { token });
    return data;
}

export async function unlockStatus() {
    const { data } = await apiGet('/api/owner/status');
    return data;
}

export async function fetchPlannerTime() {
    const { data } = await apiGet('/api/agent/planner-time');
    return data;
}

export async function setPlannerTime(at) {
    const { data } = await apiPut('/api/agent/planner-time', { at });
    return data;
}

export async function sendMessage(message, sessionId) {
    const { data } = await apiPost('/api/agent/chat', { message, session_id: sessionId });
    return data;
}

export async function fetchCommands() {
    const { data } = await apiGet('/api/agent/commands?surface=web');
    return data;
}

export async function fetchRun(runId) {
    const { data } = await apiGet(`/api/agent/run/${runId}`);
    return data;
}

export function stopRun(runId) {
    return apiPost(`/api/agent/run/${runId}/stop`);
}

export async function fetchPlanProposals() {
    const { data } = await apiGet('/api/agent/plan/proposals');
    return data;
}

export async function approve(proposalId) {
    const { data } = await apiPost('/api/agent/approve', { proposal_id: proposalId });
    return data;
}

export async function reject(proposalId, reason) {
    const { data } = await apiPost('/api/agent/reject', { proposal_id: proposalId, reason });
    return data;
}
