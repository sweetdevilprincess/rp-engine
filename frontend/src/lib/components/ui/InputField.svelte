<script lang="ts">
	/**
	 * Themed text input with focus ring.
	 *
	 * Usage:
	 *   <InputField placeholder="Search..." bind:value={query} />
	 *   <InputField placeholder="Name" size="sm" />
	 */
	import type { HTMLInputAttributes } from 'svelte/elements';

	interface Props extends Omit<HTMLInputAttributes, 'size'> {
		value?: string;
		size?: 'sm' | 'md';
	}

	let { value = $bindable(''), placeholder = '', type = 'text', size = 'md', id = undefined, ...restProps }: Props = $props();
</script>

<input
	{type}
	{id}
	{placeholder}
	bind:value
	class="w-full rounded-lg border border-border-custom bg-bg-subtle text-text placeholder:text-text-muted/60
		focus:border-accent-border focus:outline-none
		{size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm'}"
	style="font-family: 'DM Sans', system-ui, sans-serif;"
	{...restProps}
/>
