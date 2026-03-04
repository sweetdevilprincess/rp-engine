import { apiFetch } from './client';
import type { ExchangeSave, ExchangeResponse, ExchangeListResponse } from '$lib/types';

export async function listExchanges(params?: { session_id?: string; limit?: number; offset?: number }): Promise<ExchangeListResponse> {
	return apiFetch<ExchangeListResponse>('/api/exchanges', { params });
}

export async function saveExchange(body: ExchangeSave): Promise<ExchangeResponse> {
	return apiFetch<ExchangeResponse>('/api/exchanges', {
		method: 'POST',
		body: JSON.stringify(body),
	});
}
