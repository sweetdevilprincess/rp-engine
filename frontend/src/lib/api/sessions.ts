import { apiFetch } from './client';
import type { SessionCreate, SessionResponse, SessionEndResponse, SessionTimelineResponse } from '$lib/types';

export async function getActiveSession(): Promise<SessionResponse | null> {
	try {
		return await apiFetch<SessionResponse>('/api/sessions/active');
	} catch (err: any) {
		if (err.status === 404) return null;
		throw err;
	}
}

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

export async function getSessionTimeline(sessionId: string): Promise<SessionTimelineResponse> {
	return apiFetch<SessionTimelineResponse>(
		`/api/sessions/${encodeURIComponent(sessionId)}/timeline`
	);
}
