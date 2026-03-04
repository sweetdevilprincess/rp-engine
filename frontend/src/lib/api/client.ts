import { get } from 'svelte/store';
import { activeRP, activeBranch } from '$lib/stores/rp';

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string,
	) {
		super(message);
	}
}

interface FetchOptions extends RequestInit {
	params?: Record<string, string | number | boolean | undefined>;
	skipRPContext?: boolean;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
	const { params = {}, skipRPContext = false, ...init } = options;
	const query = new URLSearchParams();

	if (!skipRPContext) {
		const rp = get(activeRP);
		const branch = get(activeBranch);
		if (rp) query.set('rp_folder', rp.rp_folder);
		if (branch) query.set('branch', branch);
	}

	for (const [k, v] of Object.entries(params)) {
		if (v !== undefined) query.set(k, String(v));
	}

	const qs = query.toString();
	const url = `${path}${qs ? '?' + qs : ''}`;

	const res = await fetch(url, {
		headers: { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) },
		...init,
	});

	if (!res.ok) {
		let message = `HTTP ${res.status}`;
		try {
			const body = await res.json();
			message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
		} catch {}
		throw new ApiError(res.status, message);
	}

	return res.json() as Promise<T>;
}
