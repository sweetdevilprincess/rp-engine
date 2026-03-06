<script lang="ts">
	/**
	 * Universal pill badge for type labels, status indicators, importance tags, etc.
	 *
	 * Usage:
	 *   <Badge>main</Badge>
	 *   <Badge color="var(--color-accent)" bg="var(--color-accent-soft)">gothic</Badge>
	 *   <Badge dot="#6d8c5e">NPC</Badge>
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		color?: string;
		bg?: string;
		dot?: string;
		children?: Snippet;
	}

	let { color = 'var(--color-text-dim)', bg = 'var(--color-bg-subtle)', dot = '', children }: Props = $props();
</script>

<span
	class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium leading-tight"
	style="color: {color}; background: {bg};"
>
	{#if dot}
		<span class="h-1.5 w-1.5 shrink-0 rounded-full" style="background: {dot};"></span>
	{/if}
	{@render children?.()}
</span>
