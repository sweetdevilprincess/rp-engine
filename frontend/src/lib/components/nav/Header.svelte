<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { activeRP } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import BranchIndicator from './BranchIndicator.svelte';

	const navLinks = [
		{ path: '/',            label: 'Home',        rpRequired: false },
		{ path: '/cards',       label: 'Cards',       rpRequired: true  },
		{ path: '/sessions',    label: 'Sessions',    rpRequired: true  },
		{ path: '/generations', label: 'Generations', rpRequired: true  },
		{ path: '/dashboard',   label: 'Dashboard',   rpRequired: true  },
		{ path: '/npc',         label: 'Trust',       rpRequired: true  },
		{ path: '/dev',         label: 'Dev',         rpRequired: true  },
		{ path: '/settings',    label: 'Settings',    rpRequired: false },
	];

	function getHref(link: (typeof navLinks)[0]): string {
		if (!link.rpRequired) return link.path;
		if (!$activeRP) return '#';
		return `/${$activeRP.rp_folder}${link.path}`;
	}

	function isActive(link: (typeof navLinks)[0]): boolean {
		if (link.path === '/') return $page.url.pathname === '/';
		if (!$activeRP) return false;
		return $page.url.pathname.startsWith(`/${$activeRP.rp_folder}${link.path}`);
	}

	function isDisabled(link: (typeof navLinks)[0]): boolean {
		return link.rpRequired && !$activeRP;
	}
</script>

<header class="h-14 bg-surface border-b border-border-custom flex items-center px-4 gap-4 shrink-0 z-40">
	<!-- Logo -->
	<a
		href="/"
		class="w-9 h-9 rounded-full border-2 border-accent flex items-center justify-center
			text-accent font-bold text-sm hover:bg-accent/10 transition-colors shrink-0"
	>
		RP
	</a>

	<!-- Nav links -->
	<nav class="flex items-center gap-0.5 flex-1">
		{#each navLinks as link}
			{#if isDisabled(link)}
				<span class="px-3 py-1.5 rounded-md text-sm text-text-dim/30 cursor-not-allowed select-none">
					{link.label}
				</span>
			{:else}
				<a
					href={getHref(link)}
					class="px-3 py-1.5 rounded-md text-sm transition-colors
						{isActive(link)
							? 'bg-accent/20 text-accent'
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
				>
					{link.label}
				</a>
			{/if}
		{/each}
	</nav>

	<!-- Right side: active RP name + branch + server status -->
	<div class="flex items-center gap-3 shrink-0">
		{#if $activeRP}
			<button
				class="text-sm text-text-dim hover:text-text transition-colors"
				on:click={() => goto(`/${$activeRP!.rp_folder}/`)}
				title="Go to RP overview"
			>
				{$activeRP.rp_folder}
			</button>
			<BranchIndicator />
		{/if}
		<span
			class="w-2 h-2 rounded-full shrink-0 {$serverHealth.status === 'online' ? 'bg-success' : 'bg-error'}"
			title="Server {$serverHealth.status}"
		></span>
	</div>
</header>
