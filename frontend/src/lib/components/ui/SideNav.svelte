<script lang="ts">
	/**
	 * Vertical sidebar navigation with title and selectable items.
	 *
	 * Usage:
	 *   <SideNav title="Dashboard" items={tools} bind:active={activeTool} onselect={handleSelect} />
	 *   <SideNav title="Cards" width="w-[260px]">...custom content...</SideNav>
	 */
	import type { Snippet } from 'svelte';
	import SectionLabel from './SectionLabel.svelte';

	interface Props {
		title?: string;
		items?: { id: string; label: string }[];
		active?: string;
		width?: string;
		onselect?: (id: string) => void;
		children?: Snippet;
	}

	let { title = '', items = [], active = $bindable(''), width = 'w-[160px]', onselect, children }: Props = $props();

	function select(id: string) {
		active = id;
		onselect?.(id);
	}
</script>

<nav class="{width} shrink-0 bg-surface border border-border-custom rounded-[10px] overflow-hidden">
	{#if title}
		<div class="px-3 py-2 border-b border-border-custom/60">
			<SectionLabel>{title}</SectionLabel>
		</div>
	{/if}
	{#if items.length > 0}
		<div class="p-1">
			{#each items as item}
				<button
					class="w-full flex items-center gap-2 px-2.5 py-[7px] rounded-md text-xs text-left transition-all
						{active === item.id
							? 'bg-accent/10 text-accent font-semibold'
							: 'text-text-dim hover:text-text hover:bg-surface2/50'}"
					onclick={() => select(item.id)}
				>
					<span>{item.label}</span>
				</button>
			{/each}
		</div>
	{/if}
	{#if children}{@render children()}{/if}
</nav>
