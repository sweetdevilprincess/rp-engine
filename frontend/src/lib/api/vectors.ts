import { apiFetch } from './client';
import type { ChunkRow, VectorStats, DebugSearchResult, ExchangeChunk } from '$lib/types';

export type { ExchangeChunk };

export async function getVectorStats(): Promise<VectorStats> {
	return apiFetch<VectorStats>('/api/vectors/stats');
}

export async function listChunks(params?: {
	card_type?: string;
	file_path?: string;
	limit?: number;
	offset?: number;
}): Promise<ChunkRow[]> {
	return apiFetch<ChunkRow[]>('/api/vectors/chunks', { params });
}

export async function getChunksForFile(file_path: string): Promise<ChunkRow[]> {
	return apiFetch<ChunkRow[]>(`/api/vectors/chunks/${encodeURIComponent(file_path)}`);
}

export async function listExchangeChunks(params?: {
	rp_folder?: string;
	branch?: string;
	limit?: number;
}): Promise<ExchangeChunk[]> {
	return apiFetch<ExchangeChunk[]>('/api/vectors/exchange-chunks', { params });
}

export async function reindexExchanges(params?: {
	rp_folder?: string;
	branch?: string;
}): Promise<{ status: string; total_exchanges: number; embedded: number; failed: number }> {
	return apiFetch('/api/vectors/reindex-exchanges', {
		method: 'POST',
		params,
	});
}

export async function searchDebug(
	query: string,
	limit = 10,
): Promise<DebugSearchResult[]> {
	return apiFetch<DebugSearchResult[]>('/api/vectors/search-debug', {
		method: 'POST',
		body: JSON.stringify({ query, limit }),
		skipRPContext: false, // rp_folder injected automatically from store
	});
}
