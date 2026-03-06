<script lang="ts">
	import ContextInspector from '$lib/components/dev/ContextInspector.svelte';
	import ChunkViewer from '$lib/components/dev/ChunkViewer.svelte';
	import SideNav from '$lib/components/ui/SideNav.svelte';

	const tools = [
		{ id: 'context', label: 'Context Inspector' },
		{ id: 'chunks',  label: 'Chunk Viewer' },
	];

	let activeTool = $state('context');
</script>

<div class="flex gap-3">
	<SideNav title="Dev Tools" items={tools} bind:active={activeTool} />

	<div class="flex-1 min-w-0">
		{#if activeTool === 'context'}
			<ContextInspector />
		{:else if activeTool === 'chunks'}
			<ChunkViewer />
		{/if}
	</div>
</div>
