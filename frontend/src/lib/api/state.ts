import { apiFetch } from './client';

export async function getFullState(): Promise<unknown> {
	return apiFetch('/api/state');
}
