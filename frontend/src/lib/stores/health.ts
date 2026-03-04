import { writable } from 'svelte/store';

export type ServerStatus = 'checking' | 'online' | 'offline';
export interface HealthState {
	status: ServerStatus;
	data: { version: string; indexed_cards: number | null } | null;
}
export const serverHealth = writable<HealthState>({ status: 'checking', data: null });
