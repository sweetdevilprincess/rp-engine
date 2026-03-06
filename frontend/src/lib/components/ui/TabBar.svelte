<script lang="ts">
	/**
	 * Horizontal tab bar with active state styling.
	 *
	 * Usage:
	 *   <TabBar items={[{id: 'a', label: 'Tab A'}, {id: 'b', label: 'Tab B'}]} bind:active={tab} />
	 */
	interface Props {
		items: { id: string; label: string }[];
		active?: string;
		onselect?: (id: string) => void;
	}

	let { items, active = $bindable(''), onselect }: Props = $props();

	function select(id: string) {
		active = id;
		onselect?.(id);
	}
</script>

<div class="flex bg-surface border border-border-custom rounded-lg overflow-hidden">
	{#each items as item, i}
		<button
			class="px-4 py-2 text-sm transition-colors
				{i > 0 ? 'border-l border-border-custom' : ''}
				{active === item.id
					? 'bg-accent/10 text-accent font-medium'
					: 'text-text-dim hover:text-text hover:bg-bg-subtle'}"
			onclick={() => select(item.id)}
		>{item.label}</button>
	{/each}
</div>
