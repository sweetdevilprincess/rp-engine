<script lang="ts">
	/**
	 * Boolean toggle switch with label.
	 *
	 * Usage:
	 *   <Toggle label="Integrate User Narrative" bind:checked={integrating} />
	 */
	interface Props {
		label?: string;
		checked?: boolean;
	}

	let { label = '', checked = $bindable(false) }: Props = $props();
</script>

<button
	class="toggle-wrap"
	role="switch"
	aria-checked={checked}
	aria-label={label}
	onclick={() => (checked = !checked)}
>
	<span class="track" class:track-on={checked}>
		<span class="thumb" class:thumb-on={checked}></span>
	</span>
	{#if label}
		<span class="text-xs text-text-dim">{label}</span>
	{/if}
</button>

<style>
	.toggle-wrap {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		border: none;
		background: none;
		padding: 0;
		font-family: inherit;
	}
	.track {
		position: relative;
		width: 36px;
		height: 20px;
		border-radius: 10px;
		background: var(--color-bg-subtle);
		border: 1px solid var(--color-border-custom);
		transition: background 0.2s, border-color 0.2s;
		flex-shrink: 0;
	}
	.track-on {
		background: var(--color-accent);
		border-color: var(--color-accent-border);
	}
	.thumb {
		position: absolute;
		top: 1px;
		left: 1px;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--color-surface-raised);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
		transition: left 0.2s ease;
	}
	.thumb-on {
		left: 17px;
	}
</style>
