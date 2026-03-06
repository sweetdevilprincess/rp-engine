import { apiFetch } from './client';
import type { CustomStateSchema, CustomStateValue, CustomStateSnapshot, PresetInfo } from '$lib/types';

export type { CustomStateSchema, CustomStateValue, CustomStateSnapshot, PresetInfo };

export async function listSchemas(rp_folder: string): Promise<CustomStateSchema[]> {
	return apiFetch<CustomStateSchema[]>('/api/custom-state/schemas', {
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function getCustomStateSnapshot(
	rp_folder: string,
	branch = 'main',
): Promise<CustomStateSnapshot> {
	return apiFetch<CustomStateSnapshot>('/api/custom-state', {
		params: { rp_folder, branch },
		skipRPContext: true,
	});
}

export async function setCustomStateValue(
	schema_id: string,
	body: { rp_folder: string; branch?: string; entity_id?: string; value: unknown; reason?: string },
): Promise<CustomStateValue> {
	return apiFetch<CustomStateValue>(`/api/custom-state/${encodeURIComponent(schema_id)}`, {
		method: 'POST',
		body: JSON.stringify({ schema_id, ...body }),
		skipRPContext: true,
	});
}

export async function listPresets(): Promise<PresetInfo[]> {
	return apiFetch<PresetInfo[]>('/api/custom-state/presets/list', {
		skipRPContext: true,
	});
}

export async function applyPreset(
	preset_name: string,
	rp_folder: string,
): Promise<CustomStateSchema[]> {
	return apiFetch<CustomStateSchema[]>(
		`/api/custom-state/presets/${encodeURIComponent(preset_name)}/apply`,
		{
			method: 'POST',
			params: { rp_folder },
			skipRPContext: true,
		},
	);
}
