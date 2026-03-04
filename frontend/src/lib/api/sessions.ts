import { apiFetch } from './client';
import type { SessionCreate, SessionResponse, SessionEndResponse } from '$lib/types';

export async function startSession(body: SessionCreate): Promise<SessionResponse> {
	return apiFetch<SessionResponse>('/api/sessions', {
		method: 'POST',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function endSession(sessionId: string): Promise<SessionEndResponse> {
	return apiFetch<SessionEndResponse>(`/api/sessions/${encodeURIComponent(sessionId)}/end`, {
		method: 'POST',
	});
}
