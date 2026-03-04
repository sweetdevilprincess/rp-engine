import { apiFetch } from './client';
import type { ChunkRow, VectorStats, DebugSearchResult } from '$lib/types';

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
