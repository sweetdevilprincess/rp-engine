<script lang="ts">
	/**
	 * Standardized empty / error / loading state display.
	 *
	 * Usage:
	 *   <EmptyState message="No cards found." />
	 *   <EmptyState message="Could not connect" variant="error" />
	 *   <EmptyState message="Loading..." variant="loading" />
	 */
	interface Props {
		message?: string;
		variant?: 'empty' | 'error' | 'loading';
	}

	let { message = 'Nothing to show', variant = 'empty' }: Props = $props();

	let classes = $derived([
		'rounded-[10px] p-8 text-center text-sm border',
		variant === 'error'
			? 'bg-error/10 border-error/30 text-error'
			: 'bg-surface border-border-custom text-text-dim',
		variant === 'loading' ? 'animate-pulse' : '',
	].join(' '));
</script>

<div class={classes}>
	{message}
</div>
