<script lang="ts">
	/**
	 * Raised surface card with optional hover highlight.
	 *
	 * Usage:
	 *   <Card>content</Card>
	 *   <Card hover onclick={handler}>clickable card</Card>
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		hover?: boolean;
		padding?: string;
		children?: Snippet;
	}

	let { hover = false, padding = '', children, ...restProps }: Props = $props();
</script>

{#if restProps.onclick || hover}
<div
	class="card card-hover"
	style={padding ? `padding: ${padding};` : ''}
	role="button"
	tabindex="0"
	onkeydown={(e: KeyboardEvent) => {
		if ((e.key === 'Enter' || e.key === ' ') && restProps.onclick) {
			e.preventDefault();
			(restProps.onclick as (e: Event) => void)(e);
		}
	}}
	{...restProps}
>
	{@render children?.()}
</div>
{:else}
<div
	class="card"
	style={padding ? `padding: ${padding};` : ''}
	{...restProps}
>
	{@render children?.()}
</div>
{/if}

<style>
	.card {
		background: var(--color-surface-raised);
		border-radius: 10px;
		border: 1px solid var(--color-border-custom);
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
	}
	.card-hover {
		cursor: pointer;
	}
	.card-hover:hover {
		border-color: var(--color-accent-border);
		box-shadow: 0 3px 16px rgba(109, 140, 94, 0.10), 0 1px 3px rgba(0, 0, 0, 0.04);
	}
</style>
