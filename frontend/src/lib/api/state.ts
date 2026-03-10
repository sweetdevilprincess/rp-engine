import { apiFetch } from './client';
import type { StateSnapshot, CharacterDetail, SceneStateDetail, RelationshipDetail, RelationshipGraphResponse } from '$lib/types';

export async function getFullState(): Promise<StateSnapshot> {
	return apiFetch<StateSnapshot>('/api/state');
}

export async function updateCharacter(
	name: string,
	body: { location?: string; emotional_state?: string; conditions?: string[] },
): Promise<CharacterDetail> {
	return apiFetch<CharacterDetail>(`/api/state/characters/${encodeURIComponent(name)}`, {
		method: 'PUT',
		body: JSON.stringify(body),
	});
}

export async function updateScene(
	body: { location?: string; time_of_day?: string; mood?: string; in_story_timestamp?: string },
): Promise<SceneStateDetail> {
	return apiFetch<SceneStateDetail>('/api/state/scene', {
		method: 'PUT',
		body: JSON.stringify(body),
	});
}

export async function getRelationshipGraph(
	povCharacter?: string,
): Promise<RelationshipGraphResponse> {
	return apiFetch<RelationshipGraphResponse>('/api/state/relationship-graph', {
		params: povCharacter ? { pov_character: povCharacter } : undefined,
	});
}

export async function adjustTrust(
	charA: string,
	charB: string,
	body: { trust_change: number; reason: string; direction?: string },
): Promise<RelationshipDetail> {
	return apiFetch<RelationshipDetail>(
		`/api/state/relationships/${encodeURIComponent(charA)}/${encodeURIComponent(charB)}`,
		{ method: 'PUT', body: JSON.stringify(body) },
	);
}
