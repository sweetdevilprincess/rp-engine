<script lang="ts">
	/**
	 * Clickable entity/relationship chip.
	 *
	 * Usage:
	 *   <EntityChip label="ally" name="Viktor" onclick={() => selectCard('Viktor')} />
	 *   <EntityChip label="owns" name="Dagger" variant="subtle" onclick={fn} />
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		label?: string;
		name?: string;
		variant?: 'default' | 'subtle';
		onclick?: () => void;
		children?: Snippet;
	}

	let { label, name, variant = 'default', onclick, children }: Props = $props();
</script>

<button
	class="flex items-center gap-1.5 text-xs rounded-lg transition-colors cursor-pointer
		{variant === 'default'
			? 'px-3 py-1.5 border border-border-custom bg-surface2/50 hover:border-accent/40'
			: 'px-2.5 py-1.5 bg-bg-subtle hover:bg-accent/10'}"
	{onclick}
>
	{#if label}
		<span class="text-text-dim/60 text-[10px]">{label}</span>
	{/if}
	{#if name}
		<span class="text-accent font-medium">{name}</span>
	{/if}
	{#if children}{@render children()}{/if}
</button>
