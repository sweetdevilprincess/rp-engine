import { apiFetch } from './client';
import type { NPCListItem, TrustInfo, NPCReaction } from '$lib/types';

export async function listNPCs(pov_character?: string): Promise<NPCListItem[]> {
	return apiFetch<NPCListItem[]>('/api/npcs', { params: { pov_character } });
}

export async function getTrustInfo(name: string, target_name?: string): Promise<TrustInfo> {
	return apiFetch<TrustInfo>(`/api/npc/${encodeURIComponent(name)}/trust`, {
		params: { target_name },
	});
}

export async function getNPCReaction(npc_name: string, scene_prompt: string, pov_character?: string): Promise<NPCReaction> {
	return apiFetch<NPCReaction>('/api/npc/react', {
		method: 'POST',
		body: JSON.stringify({ npc_name, scene_prompt, pov_character }),
	});
}

export async function batchNPCReactions(npc_names: string[], scene_prompt: string, pov_character?: string): Promise<NPCReaction[]> {
	return apiFetch<NPCReaction[]>('/api/npc/react-batch', {
		method: 'POST',
		body: JSON.stringify({ npc_names, scene_prompt, pov_character }),
	});
}
