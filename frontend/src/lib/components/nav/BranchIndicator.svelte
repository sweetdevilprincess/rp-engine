<script lang="ts">
	import { activeRP, activeBranch } from '$lib/stores/rp';

	let showDropdown = false;

	function selectBranch(branch: string) {
		activeBranch.set(branch);
		showDropdown = false;
	}
</script>

{#if $activeRP}
	<div class="relative">
		<button
			class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-colors"
			onclick={() => (showDropdown = !showDropdown)}
		>
			<span class="w-1.5 h-1.5 rounded-full bg-success"></span>
			{$activeBranch}
		</button>

		{#if showDropdown && $activeRP.branches.length > 1}
			<div class="absolute top-full left-0 mt-1 w-40 bg-bg-subtle border border-border-custom rounded-md shadow-lg z-50">
				{#each $activeRP.branches as branch}
					<button
						class="block w-full text-left px-3 py-1.5 text-sm hover:bg-bg-subtle transition-colors
							{branch === $activeBranch ? 'text-accent' : 'text-text-dim'}"
						onclick={() => selectBranch(branch)}
					>
						{branch}
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}
