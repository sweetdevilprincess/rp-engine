<script lang="ts">
	/**
	 * Label + input wrapper for form fields.
	 *
	 * Usage:
	 *   <FormField label="Name" id="rp-name">
	 *     <InputField id="rp-name" bind:value={name} />
	 *   </FormField>
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		label: string;
		id?: string;
		required?: boolean;
		size?: 'sm' | 'xs';
		children?: Snippet;
	}

	let { label, id, required = false, size = 'sm', children }: Props = $props();

	const sizeClass: Record<string, string> = {
		sm: 'text-sm',
		xs: 'text-xs',
	};
</script>

<div>
	<label class="block {sizeClass[size]} font-medium text-text-dim mb-1" for={id}>
		{label}{#if required}<span class="text-error ml-0.5">*</span>{/if}
	</label>
	{#if children}{@render children()}{/if}
</div>
