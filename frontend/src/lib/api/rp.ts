import { apiFetch } from './client';
import type { RPCreate, RPResponse, RPInfo } from '$lib/types';

export async function listRPs(): Promise<RPInfo[]> {
	return apiFetch<RPInfo[]>('/api/rp', { skipRPContext: true });
}

export async function getRP(name: string): Promise<RPInfo> {
	return apiFetch<RPInfo>(`/api/rp/${encodeURIComponent(name)}`, { skipRPContext: true });
}

export async function createRP(body: RPCreate): Promise<RPResponse> {
	return apiFetch<RPResponse>('/api/rp', {
		method: 'POST',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}
