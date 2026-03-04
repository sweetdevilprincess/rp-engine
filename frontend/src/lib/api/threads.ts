import { apiFetch } from './client';
import type { ThreadListResponse, ThreadDetail, ThreadCounterUpdate } from '$lib/types';

export async function listThreads(): Promise<ThreadListResponse> {
	return apiFetch<ThreadListResponse>('/api/threads');
}

export async function getThread(threadId: string): Promise<ThreadDetail> {
	return apiFetch<ThreadDetail>(`/api/threads/${encodeURIComponent(threadId)}`);
}

export async function updateThreadCounter(threadId: string, counter: number): Promise<ThreadCounterUpdate> {
	return apiFetch<ThreadCounterUpdate>(`/api/threads/${encodeURIComponent(threadId)}/update-counter`, {
		method: 'POST',
		body: JSON.stringify({ counter }),
	});
}

export async function getAlerts(): Promise<unknown> {
	return apiFetch('/api/threads/alerts');
}
