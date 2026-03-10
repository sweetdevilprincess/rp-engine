<script lang="ts">
	/**
	 * Modal confirmation dialog.
	 *
	 * Usage:
	 *   <ConfirmDialog
	 *     open={showConfirm}
	 *     title="Large Trust Change"
	 *     message="Are you sure you want to adjust trust by +8?"
	 *     variant="danger"
	 *     onConfirm={handleConfirm}
	 *     onCancel={() => showConfirm = false}
	 *   />
	 */
	import { Dialog } from 'bits-ui';

	interface Props {
		open: boolean;
		title: string;
		message: string;
		confirmLabel?: string;
		variant?: 'default' | 'danger';
		onConfirm: () => void;
		onCancel: () => void;
	}

	let { open = $bindable(false), title, message, confirmLabel = 'Confirm', variant = 'default', onConfirm, onCancel }: Props = $props();
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) onCancel(); }}>
	<Dialog.Portal>
		<Dialog.Overlay class="fixed inset-0 bg-black/50 z-50" />
		<Dialog.Content class="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50
			bg-surface border border-border-custom rounded-lg p-6 max-w-sm w-full mx-4 space-y-4 shadow-xl">
			<Dialog.Title class="text-base font-semibold text-text">{title}</Dialog.Title>
			<Dialog.Description class="text-sm text-text-dim">{message}</Dialog.Description>
			<div class="flex gap-3 pt-2">
				<button
					class="flex-1 text-sm font-medium py-2 rounded-lg transition-colors
						{variant === 'danger'
							? 'bg-error hover:bg-error/80 text-text-on-accent'
							: 'bg-accent hover:bg-accent-hover text-text-on-accent'}"
					onclick={() => { onConfirm(); open = false; }}
				>{confirmLabel}</button>
				<button
					class="flex-1 bg-bg-subtle hover:bg-bg-subtle/80 text-text text-sm py-2 rounded-lg
						border border-border-custom transition-colors"
					onclick={() => { onCancel(); open = false; }}
				>Cancel</button>
			</div>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
