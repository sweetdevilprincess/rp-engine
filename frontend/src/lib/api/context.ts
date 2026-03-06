import { apiFetch } from './client';
import type { ContextResponse, GuidelinesResponse } from '$lib/types';

export async function getSceneContext(user_message: string, last_response?: string, session_id?: string): Promise<ContextResponse> {
	return apiFetch<ContextResponse>('/api/context', {
		method: 'POST',
		body: JSON.stringify({ user_message, last_response, session_id }),
	});
}

export async function resolveContext(scene_description: string, keywords?: string[], max_hops?: number, max_results?: number): Promise<unknown> {
	return apiFetch('/api/context/resolve', {
		method: 'POST',
		body: JSON.stringify({ scene_description, keywords, max_hops, max_results }),
	});
}

export async function getGuidelines(rp_folder: string): Promise<GuidelinesResponse> {
	return apiFetch<GuidelinesResponse>('/api/context/guidelines', {
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function updateGuidelines(
	rp_folder: string,
	body: Partial<GuidelinesResponse>,
): Promise<GuidelinesResponse> {
	return apiFetch<GuidelinesResponse>('/api/context/guidelines', {
		method: 'PUT',
		params: { rp_folder },
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}
