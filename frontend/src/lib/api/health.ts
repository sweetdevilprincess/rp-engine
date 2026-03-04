import { apiFetch } from './client';

export interface HealthResponse {
	version: string;
	indexed_cards: number | null;
}

export async function checkHealth(): Promise<HealthResponse> {
	return apiFetch<HealthResponse>('/health', { skipRPContext: true });
}
