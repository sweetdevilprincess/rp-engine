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

/** Build a query string from key-value pairs, omitting undefined values. */
export function buildQueryString(
	params: Record<string, string | number | boolean | undefined>,
): string {
	const query = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v !== undefined) query.set(k, String(v));
	}
	const qs = query.toString();
	return qs ? '?' + qs : '';
}

/** Extract an error detail message from a failed fetch Response. */
export async function extractErrorDetail(res: Response): Promise<string> {
	let message = `HTTP ${res.status}`;
	try {
		const body = await res.json();
		message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
	} catch {}
	return message;
}

/** Build a URL with RP context query params and inject rp_folder/branch into a JSON body object. */
export function buildRPRequest(
	path: string,
	body?: Record<string, unknown>,
	params?: Record<string, string | number | boolean | undefined>,
): { url: string; body?: Record<string, unknown> } {
	const rp = get(activeRP);
	const branch = get(activeBranch);
	const rpParams: Record<string, string | number | boolean | undefined> = { ...params };
	if (rp) rpParams.rp_folder = rp.rp_folder;
	if (branch) rpParams.branch = branch;
	const url = `${path}${buildQueryString(rpParams)}`;

	if (body && rp) {
		if (!('rp_folder' in body)) body.rp_folder = rp.rp_folder;
		if (branch && !('branch' in body)) body.branch = branch;
	}

	return { url, body };
}

interface FetchOptions extends RequestInit {
	params?: Record<string, string | number | boolean | undefined>;
	skipRPContext?: boolean;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
	const { params = {}, skipRPContext = false, ...init } = options;
	let url: string;

	if (!skipRPContext) {
		// Inject RP context into query params and body
		const method = (init.method ?? 'GET').toUpperCase();
		let bodyObj: Record<string, unknown> | undefined;
		if (init.body && typeof init.body === 'string' && ['POST', 'PUT', 'PATCH'].includes(method)) {
			try {
				const parsed = JSON.parse(init.body);
				if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
					bodyObj = parsed;
				}
			} catch {}
		}

		const built = buildRPRequest(path, bodyObj, params);
		url = built.url;
		if (bodyObj) init.body = JSON.stringify(built.body ?? bodyObj);
	} else {
		url = `${path}${buildQueryString(params)}`;
	}

	const res = await fetch(url, {
		headers: { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) },
		...init,
	});

	if (!res.ok) {
		throw new ApiError(res.status, await extractErrorDetail(res));
	}

	return res.json() as Promise<T>;
}
