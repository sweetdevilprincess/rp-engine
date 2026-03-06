<script lang="ts">
	/**
	 * Flex header row with left-side title + right-side actions.
	 *
	 * Usage:
	 *   <PageHeader title="RP Engine" />
	 *   <PageHeader title="Cards" size="md">
	 *     {#snippet before()}<Badge>NPC</Badge>{/snippet}
	 *     {#snippet actions()}<Btn small>Edit</Btn>{/snippet}
	 *   </PageHeader>
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		title?: string;
		subtitle?: string;
		size?: 'lg' | 'md' | 'sm';
		before?: Snippet;
		badges?: Snippet;
		actions?: Snippet;
	}

	let { title, subtitle, size = 'lg', before, badges, actions }: Props = $props();

	const headingClass: Record<string, string> = {
		lg: 'text-2xl font-bold text-text font-serif',
		md: 'text-lg font-semibold text-text font-serif m-0',
		sm: 'text-base font-semibold text-text font-serif m-0',
	};
</script>

<div class="flex items-center justify-between">
	<div class="flex items-center gap-2 min-w-0">
		{#if before}{@render before()}{/if}
		{#if title}
			{#if size === 'lg'}
				<h1 class={headingClass[size]}>{title}</h1>
			{:else if size === 'md'}
				<h2 class={headingClass[size]}>{title}</h2>
			{:else}
				<h3 class={headingClass[size]}>{title}</h3>
			{/if}
		{/if}
		{#if badges}{@render badges()}{/if}
	</div>
	{#if actions}
		<div class="flex items-center gap-2 shrink-0">
			{@render actions()}
		</div>
	{/if}
</div>
{#if subtitle}
	<p class="text-xs text-text-dim mt-0.5">{subtitle}</p>
{/if}
