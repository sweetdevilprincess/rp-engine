<script lang="ts">
	/**
	 * Card wrapper with optional titled header and content area.
	 *
	 * Usage:
	 *   <CardSection title="Scene">content</CardSection>
	 *   <CardSection title="Characters" subtitle="All characters in the current RP state.">
	 *     {#snippet actions()}<button>Refresh</button>{/snippet}
	 *     content here
	 *   </CardSection>
	 *   <CardSection compact title="Scene">compact SectionLabel header</CardSection>
	 */
	import type { Snippet } from 'svelte';
	import SectionLabel from './SectionLabel.svelte';

	interface Props {
		title?: string;
		subtitle?: string;
		compact?: boolean;
		actions?: Snippet;
		children?: Snippet;
	}

	let { title, subtitle, compact = false, actions, children }: Props = $props();
</script>

<div class="bg-surface rounded-[10px] border border-border-custom overflow-hidden">
	{#if title}
		<div class="px-4 {compact ? 'py-2.5' : 'py-3'} border-b {compact ? 'border-border-custom/60' : 'border-border-custom'} {actions ? 'flex items-center justify-between' : ''}">
			{#if compact}
				<SectionLabel>{title}</SectionLabel>
			{:else if actions}
				<div>
					<h2 class="text-sm font-semibold text-text">{title}</h2>
					{#if subtitle}<p class="text-xs text-text-dim mt-0.5">{subtitle}</p>{/if}
				</div>
			{:else}
				<h2 class="text-sm font-semibold text-text">{title}</h2>
				{#if subtitle}<p class="text-xs text-text-dim mt-0.5">{subtitle}</p>{/if}
			{/if}
			{#if actions}{@render actions()}{/if}
		</div>
	{/if}
	{#if children}{@render children()}{/if}
</div>
