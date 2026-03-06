<script lang="ts">
	/**
	 * Back navigation button with left chevron.
	 *
	 * Usage:
	 *   <BackButton onclick={() => selected = null} />
	 *   <BackButton label="Back to library" onclick={goBack} />
	 */
	interface Props {
		label?: string;
		onclick?: () => void;
	}

	let { label = 'Back', onclick }: Props = $props();
</script>

<button
	class="flex items-center gap-1.5 text-sm text-text-dim hover:text-text transition-colors"
	{onclick}
>
	<svg class="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
		<path d="M10 4L6 8l4 4" />
	</svg>
	{label}
</button>
