<script lang="ts">
	/**
	 * Collapsible section with chevron toggle.
	 *
	 * Usage:
	 *   <Expandable bind:expanded={show}>
	 *     {#snippet header()}Section Title{/snippet}
	 *     Expanded content here
	 *   </Expandable>
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		expanded?: boolean;
		borderless?: boolean;
		header?: Snippet;
		children?: Snippet;
	}

	let { expanded = $bindable(false), borderless = false, header, children }: Props = $props();
</script>

<div class={borderless ? '' : 'border-t border-border-custom'}>
	<button
		class="w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-subtle transition-colors text-left"
		onclick={() => (expanded = !expanded)}
	>
		<div class="flex-1 min-w-0">
			{#if header}{@render header()}{/if}
		</div>
		<svg
			class="w-4 h-4 text-text-dim shrink-0 transition-transform {expanded ? 'rotate-180' : ''}"
			viewBox="0 0 16 16"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
		>
			<path d="M4 6l4 4 4-4" />
		</svg>
	</button>
	{#if expanded}
		<div>
			{#if children}{@render children()}{/if}
		</div>
	{/if}
</div>
