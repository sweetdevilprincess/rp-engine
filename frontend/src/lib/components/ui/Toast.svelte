<script lang="ts">
	import type { Toast } from '$lib/stores/ui';
	import { removeToast } from '$lib/stores/ui';

	interface Props {
		toast: Toast;
	}

	let { toast }: Props = $props();

	const borderColors: Record<string, string> = {
		success: 'var(--color-success)',
		error:   'var(--color-error)',
		warning: 'var(--color-warm)',
		info:    'var(--color-accent)',
	};
</script>

<div
	class="toast"
	style="border-left-color: {borderColors[toast.type] ?? borderColors.info};"
>
	<span class="flex-1 text-sm text-text">{toast.message}</span>
	<button
		class="text-text-dim hover:text-text text-lg leading-none"
		onclick={() => removeToast(toast.id)}
	>
		&times;
	</button>
</div>

<style>
	.toast {
		background: var(--color-surface-raised);
		border: 1px solid var(--color-border-custom);
		border-left-width: 4px;
		border-radius: 8px;
		padding: 12px;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
		display: flex;
		align-items: flex-start;
		gap: 8px;
	}
</style>
