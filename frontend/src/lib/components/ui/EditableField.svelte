<script lang="ts">
	/**
	 * Click-to-edit field with 4 states: display → editing → saving → error.
	 *
	 * Usage:
	 *   <EditableField bind:value={name} onSave={(v) => api.update(v)} />
	 *   <EditableField bind:value={bio} inputType="textarea" label="Bio" onSave={...} />
	 */

	interface Props {
		value: string;
		label?: string;
		placeholder?: string;
		inputType?: 'text' | 'textarea';
		onSave: (newValue: string) => Promise<void>;
	}

	let { value = $bindable(''), label, placeholder = '', inputType = 'text', onSave }: Props = $props();

	type FieldState = 'display' | 'editing' | 'saving' | 'error';
	let fieldState = $state<FieldState>('display');
	let editValue = $state('');
	let errorMessage = $state('');

	function startEditing() {
		editValue = value;
		fieldState = 'editing';
	}

	function cancel() {
		fieldState = 'display';
		errorMessage = '';
	}

	async function save() {
		if (editValue === value) {
			fieldState = 'display';
			return;
		}
		fieldState = 'saving';
		errorMessage = '';
		try {
			await onSave(editValue);
			value = editValue;
			fieldState = 'display';
		} catch (err: any) {
			errorMessage = err.message ?? 'Save failed';
			fieldState = 'error';
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') cancel();
		if (e.key === 'Enter' && inputType === 'text') save();
	}
</script>

{#if fieldState === 'display'}
	<button
		class="group flex items-center gap-1.5 text-left w-full min-h-[24px] rounded px-1 -mx-1
			hover:bg-surface2/60 transition-colors cursor-pointer border-none bg-transparent"
		onclick={startEditing}
		title={label ? `Edit ${label}` : 'Click to edit'}
	>
		<span class="text-[13px] text-text flex-1 {!value ? 'text-text-dim/50 italic' : ''}">
			{value || placeholder || '(empty)'}
		</span>
		<svg class="w-3 h-3 text-text-dim/40 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" viewBox="0 0 16 16" fill="currentColor">
			<path d="M11.013 1.427a1.75 1.75 0 012.474 0l1.086 1.086a1.75 1.75 0 010 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 01-.927-.928l.929-3.25a1.75 1.75 0 01.445-.758l8.61-8.61zm1.414 1.06a.25.25 0 00-.354 0L3.463 11.098a.25.25 0 00-.064.108l-.563 1.97 1.97-.563a.25.25 0 00.108-.064l8.61-8.61a.25.25 0 000-.354l-1.086-1.086z"/>
		</svg>
	</button>
{:else}
	<div class="space-y-1">
		{#if inputType === 'textarea'}
			<textarea
				bind:value={editValue}
				onkeydown={handleKeydown}
				disabled={fieldState === 'saving'}
				{placeholder}
				rows="3"
				class="w-full px-2.5 py-1.5 rounded-lg border text-xs text-text bg-bg-subtle
					focus:outline-none focus:ring-1 focus:ring-accent resize-y
					{fieldState === 'error' ? 'border-error' : 'border-border-custom'}
					disabled:opacity-50"
			></textarea>
		{:else}
			<input
				type="text"
				bind:value={editValue}
				onkeydown={handleKeydown}
				disabled={fieldState === 'saving'}
				{placeholder}
				class="w-full px-2.5 py-1.5 rounded-lg border text-xs text-text bg-bg-subtle
					focus:outline-none focus:ring-1 focus:ring-accent
					{fieldState === 'error' ? 'border-error' : 'border-border-custom'}
					disabled:opacity-50"
			/>
		{/if}

		{#if fieldState === 'error' && errorMessage}
			<p class="text-[11px] text-error">{errorMessage}</p>
		{/if}

		<div class="flex gap-1.5">
			<button
				class="px-2 py-1 text-[11px] rounded bg-accent text-text-on-accent hover:bg-accent-hover transition-colors
					disabled:opacity-50"
				onclick={save}
				disabled={fieldState === 'saving'}
			>
				{fieldState === 'saving' ? 'Saving...' : 'Save'}
			</button>
			<button
				class="px-2 py-1 text-[11px] rounded text-text-dim hover:text-text border border-border-custom
					hover:border-border-custom transition-colors"
				onclick={cancel}
				disabled={fieldState === 'saving'}
			>
				Cancel
			</button>
		</div>
	</div>
{/if}
