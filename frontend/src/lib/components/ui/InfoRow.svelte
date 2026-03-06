<script lang="ts">
	/**
	 * Label-value pair row for info grids.
	 *
	 * Usage:
	 *   <InfoRow label="Location" value={scene.location} />
	 *   <InfoRow label="Status"><Badge>active</Badge></InfoRow>
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		label: string;
		value?: string | number | null;
		children?: Snippet;
	}

	let { label, value, children }: Props = $props();
</script>

<div class="flex justify-between text-[13px]">
	<span class="text-text-dim">{label}</span>
	{#if children}
		{@render children()}
	{:else}
		<span class="font-medium text-text">{value ?? '—'}</span>
	{/if}
</div>
