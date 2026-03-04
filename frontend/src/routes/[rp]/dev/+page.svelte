<script lang="ts">
	import ContextInspector from '$lib/components/dev/ContextInspector.svelte';
	import ChunkViewer from '$lib/components/dev/ChunkViewer.svelte';

	const tools = [
		{ id: 'context', label: 'Context Inspector', icon: '🔍' },
		{ id: 'chunks',  label: 'Chunk Viewer',      icon: '◫'  },
	];

	let activeTool = 'context';
</script>

<div class="flex gap-2">
	<!-- Left tool navigator -->
	<nav class="w-40 shrink-0 bg-surface rounded border border-border-custom overflow-hidden self-start">
		<div class="px-2 py-1.5 border-b border-border-custom">
			<span class="text-xs font-semibold text-text-dim uppercase tracking-wider">Dev Tools</span>
		</div>
		<div class="p-1 space-y-0.5">
			{#each tools as tool}
				<button
					class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left transition-colors
						{activeTool === tool.id
							? 'bg-accent/20 text-accent'
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
					on:click={() => (activeTool = tool.id)}
				>
					<span class="leading-none">{tool.icon}</span>
					<span>{tool.label}</span>
				</button>
			{/each}
		</div>
	</nav>

	<!-- Tool content -->
	<div class="flex-1 min-w-0">
		{#if activeTool === 'context'}
			<ContextInspector />
		{:else if activeTool === 'chunks'}
			<ChunkViewer />
		{/if}
	</div>
</div>
