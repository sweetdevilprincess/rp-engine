<script lang="ts">
	/**
	 * Themed tooltip wrapper around Bits UI Tooltip.
	 *
	 * Usage:
	 *   <Tooltip text="Reduces trust gains by 50%">
	 *     <Badge>Paranoid</Badge>
	 *   </Tooltip>
	 *
	 *   <!-- Rich content via snippet -->
	 *   <Tooltip>
	 *     {#snippet content()}<strong>Bold</strong> explanation{/snippet}
	 *     <Badge>Paranoid</Badge>
	 *   </Tooltip>
	 *
	 *   <!-- Positioning -->
	 *   <Tooltip text="Above" side="top">...</Tooltip>
	 */
	import { Tooltip } from 'bits-ui';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Plain text tooltip — simplest usage */
		text?: string;
		/** Rich content snippet — use when you need formatting */
		content?: Snippet;
		/** Trigger element(s) */
		children: Snippet;
		/** Placement relative to trigger */
		side?: 'top' | 'bottom' | 'left' | 'right';
		/** Delay in ms before showing */
		delay?: number;
	}

	let {
		text = '',
		content,
		children,
		side = 'top',
		delay = 300,
	}: Props = $props();
</script>

<Tooltip.Provider delayDuration={delay}>
	<Tooltip.Root>
		<Tooltip.Trigger
			class="inline-flex"
			style="all: unset; display: inline-flex; cursor: default;"
		>
			{@render children()}
		</Tooltip.Trigger>
		<Tooltip.Content
			{side}
			sideOffset={6}
			class="tooltip-content"
		>
			{#if content}
				{@render content()}
			{:else}
				{text}
			{/if}
		</Tooltip.Content>
	</Tooltip.Root>
</Tooltip.Provider>

<style>
	:global(.tooltip-content) {
		background: var(--color-surface-raised);
		color: var(--color-text);
		border: 1px solid var(--color-border-custom);
		border-radius: 6px;
		padding: 6px 10px;
		font-size: 12px;
		line-height: 1.4;
		max-width: 260px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
		z-index: 50;
		animation: tooltip-in 0.15s ease-out;
	}

	@keyframes tooltip-in {
		from {
			opacity: 0;
			transform: scale(0.96);
		}
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
</style>
