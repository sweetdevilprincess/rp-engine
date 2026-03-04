import { getRP } from '$lib/api/rp';
import { activeRP } from '$lib/stores/rp';
import { error } from '@sveltejs/kit';

export async function load({ params }: { params: { rp: string } }) {
	try {
		const rp = await getRP(params.rp);
		activeRP.set(rp);
		return { rp };
	} catch {
		throw error(404, `RP "${params.rp}" not found`);
	}
}
