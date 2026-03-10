import { apiFetch, extractErrorDetail } from './client';
import type { RPCreate, RPResponse, RPInfo, ChunkingConfig, RechunkResponse, ExportRequest, ImportResponse } from '$lib/types';

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

export function getAvatarUrl(rpFolder: string): string {
	return `/api/rp/${encodeURIComponent(rpFolder)}/avatar`;
}

export async function uploadAvatar(rpFolder: string, file: File): Promise<{ status: string; filename: string }> {
	const formData = new FormData();
	formData.append('file', file);
	const resp = await fetch(`/api/rp/${encodeURIComponent(rpFolder)}/avatar`, {
		method: 'POST',
		body: formData,
	});
	if (!resp.ok) {
		throw new Error(await extractErrorDetail(resp));
	}
	return resp.json();
}

export async function getChunking(rpFolder: string): Promise<ChunkingConfig> {
	return apiFetch<ChunkingConfig>(`/api/rp/${encodeURIComponent(rpFolder)}/chunking`, { skipRPContext: true });
}

export async function updateChunking(rpFolder: string, body: Partial<ChunkingConfig>): Promise<ChunkingConfig> {
	return apiFetch<ChunkingConfig>(`/api/rp/${encodeURIComponent(rpFolder)}/chunking`, {
		method: 'PUT',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function rechunk(rpFolder: string): Promise<RechunkResponse> {
	return apiFetch<RechunkResponse>(`/api/rp/${encodeURIComponent(rpFolder)}/rechunk`, {
		method: 'POST',
		skipRPContext: true,
	});
}

export async function exportRP(rpFolder: string, options?: ExportRequest): Promise<Blob> {
	const resp = await fetch(`/api/rp/${encodeURIComponent(rpFolder)}/export`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(options ?? {}),
	});
	if (!resp.ok) {
		throw new Error(await extractErrorDetail(resp));
	}
	return resp.blob();
}

export async function importRP(file: File): Promise<ImportResponse> {
	const formData = new FormData();
	formData.append('file', file);
	const resp = await fetch('/api/rp/import', {
		method: 'POST',
		body: formData,
	});
	if (!resp.ok) {
		throw new Error(await extractErrorDetail(resp));
	}
	return resp.json();
}
