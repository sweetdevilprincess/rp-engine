<script lang="ts">
	/**
	 * Themed button with primary (gradient sage) and secondary (border) variants.
	 *
	 * Usage:
	 *   <Btn primary onclick={save}>Save</Btn>
	 *   <Btn small>Cancel</Btn>
	 *   <Btn primary small disabled={saving}>Saving...</Btn>
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';

	interface Props extends HTMLButtonAttributes {
		primary?: boolean;
		small?: boolean;
		children?: Snippet;
	}

	let { primary = false, small = false, disabled = false, children, ...restProps }: Props = $props();
</script>

<button
	class="btn"
	class:btn-primary={primary}
	class:btn-secondary={!primary}
	class:btn-sm={small}
	class:btn-md={!small}
	{disabled}
	{...restProps}
	style="font-family: 'DM Sans', system-ui, sans-serif;"
>
	{@render children?.()}
</button>

<style>
	.btn {
		border-radius: 8px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s ease;
		white-space: nowrap;
		line-height: 1;
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.btn-sm { padding: 5px 12px; font-size: 12px; }
	.btn-md { padding: 9px 18px; font-size: 13px; }

	.btn-primary {
		border: none;
		background: linear-gradient(135deg, var(--color-accent), var(--color-accent-hover));
		color: #fff;
		font-weight: 600;
		box-shadow: 0 2px 8px rgba(109, 140, 94, 0.2);
	}
	.btn-primary:hover:not(:disabled) {
		box-shadow: 0 3px 12px rgba(109, 140, 94, 0.3);
	}
	.btn-secondary {
		border: 1px solid var(--color-border-custom);
		background: var(--color-bg);
		color: var(--color-text-dim);
	}
	.btn-secondary:hover:not(:disabled) {
		border-color: var(--color-border-warm);
		color: var(--color-text);
	}
</style>
