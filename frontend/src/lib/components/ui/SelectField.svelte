<script lang="ts">
	/**
	 * Themed select dropdown matching InputField styling.
	 *
	 * Usage:
	 *   <SelectField bind:value={mode} options={[{value: 'a', label: 'Alpha'}]} />
	 *   <SelectField bind:value={sort} options={sortOpts} size="sm" />
	 */
	interface Props {
		value?: string;
		options?: { value: string; label: string }[];
		placeholder?: string;
		size?: 'sm' | 'md';
		id?: string;
		[key: string]: unknown;
	}

	let { value = $bindable(''), options = [], placeholder = '', size = 'md', id = '', ...rest }: Props = $props();
</script>

<select
	{id}
	bind:value
	class="w-full rounded-lg border border-border-custom bg-bg text-text
		focus:border-accent-border focus:outline-none
		{size === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm'}"
	style="font-family: 'DM Sans', system-ui, sans-serif;"
	{...rest}
>
	{#if placeholder}
		<option value="">{placeholder}</option>
	{/if}
	{#each options as opt}
		<option value={opt.value}>{opt.label}</option>
	{/each}
</select>
