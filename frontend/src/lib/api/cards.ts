import { apiFetch } from './client';
import type { CardListResponse, StoryCardDetail, StoryCardCreate, StoryCardUpdate, ReindexResponse } from '$lib/types';

export async function listCards(params?: { card_type?: string; importance?: string }): Promise<CardListResponse> {
	return apiFetch<CardListResponse>('/api/cards', { params });
}

export async function getCard(type: string, name: string): Promise<StoryCardDetail> {
	return apiFetch<StoryCardDetail>(`/api/cards/${encodeURIComponent(type)}/${encodeURIComponent(name)}`);
}

export async function createCard(type: string, body: StoryCardCreate): Promise<StoryCardDetail> {
	return apiFetch<StoryCardDetail>(`/api/cards/${encodeURIComponent(type)}`, {
		method: 'POST',
		body: JSON.stringify(body),
	});
}

export async function updateCard(type: string, name: string, body: StoryCardUpdate): Promise<StoryCardDetail> {
	return apiFetch<StoryCardDetail>(`/api/cards/${encodeURIComponent(type)}/${encodeURIComponent(name)}`, {
		method: 'PUT',
		body: JSON.stringify(body),
	});
}

export async function reindex(): Promise<ReindexResponse> {
	return apiFetch<ReindexResponse>('/api/cards/reindex', { method: 'POST' });
}

export async function suggestCard(entity_name: string, card_type: string): Promise<StoryCardDetail> {
	return apiFetch<StoryCardDetail>('/api/cards/suggest', {
		method: 'POST',
		body: JSON.stringify({ entity_name, card_type }),
	});
}

export async function auditCards(mode?: string): Promise<unknown> {
	return apiFetch('/api/cards/audit', {
		method: 'POST',
		body: JSON.stringify({ mode: mode ?? 'quick' }),
	});
}

export async function validateCard(card_type: string, frontmatter: Record<string, unknown>): Promise<unknown> {
	return apiFetch('/api/cards/validate', {
		method: 'POST',
		body: JSON.stringify({ card_type, frontmatter }),
	});
}

export async function getSchema(card_type: string): Promise<unknown> {
	return apiFetch(`/api/cards/schema/${encodeURIComponent(card_type)}`);
}
