import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'warning' | 'info';
export interface Toast {
	id: string;
	type: ToastType;
	message: string;
	duration?: number;
}
export const toasts = writable<Toast[]>([]);

export function addToast(message: string, type: ToastType = 'info', duration = 4000) {
	const id = crypto.randomUUID();
	toasts.update((t) => [...t, { id, type, message, duration }]);
	setTimeout(() => removeToast(id), duration);
}
export function removeToast(id: string) {
	toasts.update((t) => t.filter((x) => x.id !== id));
}
