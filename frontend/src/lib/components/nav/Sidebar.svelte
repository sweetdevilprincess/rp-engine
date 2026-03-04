<script lang="ts">
	import { page } from '$app/stores';
	import { activeRP, activeBranch } from '$lib/stores/rp';
	import RPSelector from './RPSelector.svelte';
	import BranchIndicator from './BranchIndicator.svelte';

	const navLinks = [
		{ path: '', label: 'Dashboard', icon: '📊' },
		{ path: '/cards', label: 'Card Editor', icon: '🃏' },
		{ path: '/npc', label: 'NPC Trust Panel', icon: '👥' },
		{ path: '/branches', label: 'Branches', icon: '🌿' },
		{ path: '/sessions', label: 'Session History', icon: '📜' },
		{ path: '/threads', label: 'Plot Threads', icon: '🧵' },
		{ path: '/context', label: 'Context Inspector', icon: '🔍' },
		{ path: '/settings', label: 'Settings', icon: '⚙️' },
	];

	function isActive(linkPath: string): boolean {
		if (!$activeRP) return false;
		const fullPath = `/${$activeRP.rp_folder}${linkPath}`;
		if (linkPath === '') {
			return $page.url.pathname === fullPath || $page.url.pathname === fullPath + '/';
		}
		return $page.url.pathname.startsWith(fullPath);
	}
</script>

<aside class="w-64 h-screen bg-surface border-r border-border-custom flex flex-col shrink-0">
	<div class="p-4 border-b border-border-custom">
		<a href="/" class="text-xl font-bold text-accent hover:text-accent-hover transition-colors">
			RP Engine
		</a>
	</div>

	<div class="p-4 space-y-3 border-b border-border-custom">
		<RPSelector />
		<BranchIndicator />
	</div>

	<nav class="flex-1 p-2 space-y-0.5 overflow-y-auto">
		<a
			href="/"
			class="flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors
				{$page.url.pathname === '/' ? 'bg-accent/20 text-accent' : 'text-text-dim hover:text-text hover:bg-surface2'}"
		>
			Home
		</a>

		{#if $activeRP}
			<div class="pt-3 pb-1 px-3 text-xs font-medium text-text-dim uppercase tracking-wider">
				{$activeRP.rp_folder}
			</div>
			{#each navLinks as link}
				<a
					href="/{$activeRP.rp_folder}{link.path}"
					class="flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors
						{isActive(link.path) ? 'bg-accent/20 text-accent' : 'text-text-dim hover:text-text hover:bg-surface2'}"
				>
					{link.label}
				</a>
			{/each}
		{/if}
	</nav>
</aside>
