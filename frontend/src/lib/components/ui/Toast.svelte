<script lang="ts">
	import type { Toast } from '$lib/stores/ui';
	import { removeToast } from '$lib/stores/ui';

	export let toast: Toast;

	const borderColors: Record<string, string> = {
		success: 'border-l-success',
		error: 'border-l-error',
		warning: 'border-l-warning',
		info: 'border-l-accent',
	};
</script>

<div
	class="bg-surface2 border border-border-custom border-l-4 {borderColors[toast.type]} rounded-md p-3 shadow-lg flex items-start gap-2 animate-in slide-in-from-right"
>
	<span class="flex-1 text-sm text-text">{toast.message}</span>
	<button
		class="text-text-dim hover:text-text text-lg leading-none"
		on:click={() => removeToast(toast.id)}
	>
		&times;
	</button>
</div>
