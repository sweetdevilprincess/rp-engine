import { writable } from 'svelte/store';
import type { RPInfo } from '$lib/types';

function persisted<T>(key: string, initial: T) {
	let stored = initial;
	if (typeof localStorage !== 'undefined') {
		const raw = localStorage.getItem(key);
		if (raw) try { stored = JSON.parse(raw); } catch {}
	}
	const store = writable<T>(stored);
	store.subscribe((v) => {
		if (typeof localStorage !== 'undefined') localStorage.setItem(key, JSON.stringify(v));
	});
	return store;
}

export const activeRP = persisted<RPInfo | null>('rp_engine_active_rp', null);
export const activeBranch = persisted<string>('rp_engine_active_branch', 'main');
export const rpList = writable<RPInfo[]>([]);
