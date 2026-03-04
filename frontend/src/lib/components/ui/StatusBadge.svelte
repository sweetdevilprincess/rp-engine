<script lang="ts">
	import { serverHealth } from '$lib/stores/health';
</script>

{#if $serverHealth.status === 'checking'}
	<span class="inline-flex items-center gap-1.5 text-xs text-text-dim">
		<span class="w-2 h-2 rounded-full bg-warning animate-pulse"></span>
		Checking...
	</span>
{:else if $serverHealth.status === 'online'}
	<span class="inline-flex items-center gap-1.5 text-xs text-success">
		<span class="w-2 h-2 rounded-full bg-success"></span>
		v{$serverHealth.data?.version ?? '?'}
		{#if $serverHealth.data?.indexed_cards != null}
			&mdash; {$serverHealth.data.indexed_cards} cards indexed
		{/if}
	</span>
{:else}
	<span class="inline-flex items-center gap-1.5 text-xs text-error">
		<span class="w-2 h-2 rounded-full bg-error"></span>
		Offline
	</span>
{/if}
