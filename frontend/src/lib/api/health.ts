import { apiFetch } from './client';
import type { HealthResponse } from '$lib/types';

export type { HealthResponse };

export async function checkHealth(): Promise<HealthResponse> {
	return apiFetch<HealthResponse>('/health', { skipRPContext: true });
}
