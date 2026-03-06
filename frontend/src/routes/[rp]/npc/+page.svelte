<script lang="ts">
	import { onMount } from 'svelte';
	import { listNPCs } from '$lib/api/npc';
	import { addToast } from '$lib/stores/ui';
	import type { NPCListItem } from '$lib/types';
	import NPCTrustList from '$lib/components/ui/NPCTrustList.svelte';

	let npcs = $state<NPCListItem[]>([]);
	let loading = $state(false);

	onMount(async () => {
		loading = true;
		try {
			npcs = await listNPCs();
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load NPCs', 'error');
		} finally {
			loading = false;
		}
	});
</script>

<div class="max-w-4xl">
	<NPCTrustList {npcs} {loading} />
</div>
