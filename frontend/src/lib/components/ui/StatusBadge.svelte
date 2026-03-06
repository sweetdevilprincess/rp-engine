<script lang="ts">
	import { serverHealth } from '$lib/stores/health';
	import Badge from './Badge.svelte';
</script>

{#if $serverHealth.status === 'checking'}
	<Badge color="var(--color-warm)" bg="var(--color-warning-soft)">
		Checking...
	</Badge>
{:else if $serverHealth.status === 'online'}
	<Badge color="var(--color-accent)" bg="var(--color-success-soft)">
		v{$serverHealth.data?.version ?? '?'}
		{#if $serverHealth.data?.indexed_cards != null}
			— {$serverHealth.data.indexed_cards} indexed
		{/if}
	</Badge>
{:else}
	<Badge color="var(--color-error)" bg="var(--color-error-soft)">
		Offline
	</Badge>
{/if}
