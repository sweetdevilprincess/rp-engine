<script lang="ts">
	/**
	 * Gradient progress bar.
	 *
	 * Usage:
	 *   <ProgressBar value={72} color="var(--color-accent)" />
	 *   <ProgressBar value={15} color="var(--color-error)" height={6} />
	 */
	interface Props {
		value?: number;
		color?: string;
		height?: number;
	}

	let { value = 0, color = 'var(--color-accent)', height = 5 }: Props = $props();
</script>

<div class="overflow-hidden rounded-full bg-bg-subtle" style="height: {height}px;">
	<div
		class="h-full rounded-full transition-[width] duration-500 ease-out"
		style="width: {Math.min(100, Math.max(0, value))}%; background: linear-gradient(90deg, {color}cc, {color});"
	></div>
</div>
