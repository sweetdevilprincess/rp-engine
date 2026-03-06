<script lang="ts">
	/**
	 * Clickable list row with hover/active states.
	 *
	 * Usage:
	 *   <ListItem onclick={handleClick}>Content here</ListItem>
	 *   <ListItem active indicator="#e74c3c" onclick={fn}>Card name</ListItem>
	 *   <ListItem variant="card" onclick={fn}>Chapter content</ListItem>
	 */
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils/cn';

	interface Props {
		active?: boolean;
		variant?: 'flat' | 'card';
		indicator?: string;
		onclick?: () => void;
		children?: Snippet;
	}

	let { active = false, variant = 'flat', indicator, onclick, children }: Props = $props();

	let baseClass = $derived(cn(
		'w-full text-left transition-colors',
		variant === 'card' && 'bg-surface rounded-[10px] border border-border-custom p-4 hover:border-accent/40 hover:bg-bg-subtle/50',
		variant === 'flat' && 'flex items-center gap-2 px-3.5 py-2.5 border-none cursor-pointer',
		variant === 'flat' && (active
			? 'bg-accent/10 border-l-[2.5px] border-l-accent'
			: 'bg-transparent border-l-[2.5px] border-l-transparent hover:bg-surface2/50'),
	));
</script>

<button class={baseClass} {onclick}>
	{#if indicator}
		<span
			class="w-1.5 h-1.5 rounded-full shrink-0"
			style="background: {indicator}"
		></span>
	{/if}
	{#if children}{@render children()}{/if}
</button>
