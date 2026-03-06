import { apiFetch } from './client';
import type { AppConfig, ConfigUpdate, ActiveRPStatus } from '$lib/types';

export type { AppConfig, ConfigUpdate, ActiveRPStatus };

export async function getConfig(): Promise<AppConfig> {
	return apiFetch<AppConfig>('/api/config', { skipRPContext: true });
}

export async function updateConfig(body: ConfigUpdate): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/api/config', {
		method: 'PUT',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function getActiveRP(): Promise<ActiveRPStatus> {
	return apiFetch<ActiveRPStatus>('/api/config/active-rp', { skipRPContext: true });
}

export async function setActiveRP(enabled: boolean): Promise<ActiveRPStatus> {
	return apiFetch<ActiveRPStatus>('/api/config/active-rp', {
		method: 'POST',
		body: JSON.stringify({ enabled }),
		skipRPContext: true,
	});
}
