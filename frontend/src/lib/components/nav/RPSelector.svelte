<script lang="ts">
	import { activeRP, activeBranch, rpList } from '$lib/stores/rp';
	import type { RPInfo } from '$lib/types';

	function selectRP(event: Event) {
		const target = event.target as HTMLSelectElement;
		const selected = $rpList.find((rp) => rp.rp_folder === target.value);
		if (selected) {
			activeRP.set(selected);
			activeBranch.set('main');
		} else {
			activeRP.set(null);
		}
	}
</script>

<select
	class="w-full bg-bg border border-border-custom rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
	value={$activeRP?.rp_folder ?? ''}
	onchange={selectRP}
>
	<option value="" disabled>Select RP</option>
	{#each $rpList as rp}
		<option value={rp.rp_folder}>{rp.rp_folder}</option>
	{/each}
</select>
