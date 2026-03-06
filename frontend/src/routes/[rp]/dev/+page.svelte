<script lang="ts">
	import ContextInspector from '$lib/components/dev/ContextInspector.svelte';
	import ChunkViewer from '$lib/components/dev/ChunkViewer.svelte';
	import SideNav from '$lib/components/ui/SideNav.svelte';

	const tools = [
		{ id: 'context', label: 'Context Inspector' },
		{ id: 'chunks',  label: 'Chunk Viewer' },
	];

	let activeTool = 'context';
</script>

<div class="flex gap-3">
	<SideNav title="Dev Tools" items={tools} bind:active={activeTool} />

	<!-- Tool content — both panels side by side -->
	<div class="flex-1 min-w-0 flex flex-col lg:flex-row gap-3">
		<div class="flex-1 min-w-0 rounded-lg {activeTool === 'context' ? 'ring-1 ring-accent/30' : ''}">
			<ContextInspector />
		</div>
		<div class="flex-1 min-w-0 rounded-lg {activeTool === 'chunks' ? 'ring-1 ring-accent/30' : ''}">
			<ChunkViewer />
		</div>
	</div>
</div>
