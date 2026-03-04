<script lang="ts">
	import { onMount } from 'svelte';
	import { activeRP, activeBranch } from '$lib/stores/rp';
	import { addToast } from '$lib/stores/ui';
	import {
		listBranches, createBranch, switchBranch,
		listCheckpoints, createCheckpoint, restoreCheckpoint,
	} from '$lib/api/branches';
	import { listExchanges } from '$lib/api/exchanges';
	import type { BranchInfo, CheckpointInfo, ExchangeDetail } from '$lib/types';

	// ── Branch state ──────────────────────────────────────────
	let branches: BranchInfo[] = [];
	let checkpointMap: Record<string, CheckpointInfo[]> = {};
	let expandedBranch: string | null = null;
	let loadingBranches = false;

	// Create branch form
	let showCreate = false;
	let newName = '';
	let newDesc = '';
	let newFrom = '';
	let creating = false;

	// Checkpoint form
	let checkpointTarget: string | null = null;
	let cpName = '';
	let cpDesc = '';
	let creatingCp = false;

	// Restore confirmation
	let restoreTarget: { branch: string; checkpoint: string } | null = null;

	// ── Exchange state ────────────────────────────────────────
	let exchanges: ExchangeDetail[] = [];
	let totalExchanges = 0;
	let loadingExchanges = false;
	let exchangeOffset = 0;
	const PAGE_SIZE = 30;
	let expandedExchangeId: number | null = null;
	let searchQuery = '';

	// ── Init ─────────────────────────────────────────────────
	onMount(async () => {
		await Promise.all([loadBranches(), loadExchanges(true)]);
	});

	// ── Data loaders ─────────────────────────────────────────
	async function loadBranches() {
		if (!$activeRP) return;
		loadingBranches = true;
		try {
			const res = await listBranches($activeRP.rp_folder);
			branches = res.branches;
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load branches', 'error');
		} finally {
			loadingBranches = false;
		}
	}

	async function loadExchanges(reset = false) {
		loadingExchanges = true;
		const offset = reset ? 0 : exchangeOffset;
		try {
			const res = await listExchanges({ limit: PAGE_SIZE, offset });
			exchanges = reset ? res.exchanges : [...exchanges, ...res.exchanges];
			totalExchanges = res.total_count;
			exchangeOffset = offset + res.exchanges.length;
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load exchanges', 'error');
		} finally {
			loadingExchanges = false;
		}
	}

	// ── Branch actions ────────────────────────────────────────
	async function handleSwitchBranch(branch: BranchInfo) {
		if (!$activeRP || branch.is_active) return;
		try {
			await switchBranch(branch.name, $activeRP.rp_folder);
			activeBranch.set(branch.name);
			branches = branches.map(b => ({ ...b, is_active: b.name === branch.name }));
			expandedBranch = null;
			await loadExchanges(true);
		} catch (e: any) {
			addToast(e.message ?? 'Failed to switch branch', 'error');
		}
	}

	async function handleExpandBranch(branchName: string) {
		expandedBranch = expandedBranch === branchName ? null : branchName;
		if (expandedBranch && !checkpointMap[branchName] && $activeRP) {
			try {
				checkpointMap[branchName] = await listCheckpoints(branchName, $activeRP.rp_folder);
				checkpointMap = { ...checkpointMap };
			} catch (e: any) {
				addToast(e.message ?? 'Failed to load checkpoints', 'error');
			}
		}
	}

	async function handleCreateBranch() {
		if (!newName.trim() || !$activeRP || creating) return;
		creating = true;
		try {
			const b = await createBranch({
				name: newName.trim(),
				rp_folder: $activeRP.rp_folder,
				description: newDesc.trim() || undefined,
				branch_from: newFrom || undefined,
			});
			branches = [...branches, b];
			addToast(`Branch "${b.name}" created`, 'success');
			showCreate = false;
			newName = ''; newDesc = ''; newFrom = '';
		} catch (e: any) {
			addToast(e.message ?? 'Failed to create branch', 'error');
		} finally {
			creating = false;
		}
	}

	async function handleCreateCheckpoint(branchName: string) {
		if (!cpName.trim() || !$activeRP || creatingCp) return;
		creatingCp = true;
		try {
			const cp = await createCheckpoint(branchName, $activeRP.rp_folder, cpName.trim(), cpDesc.trim() || undefined);
			checkpointMap[branchName] = [...(checkpointMap[branchName] ?? []), cp];
			checkpointMap = { ...checkpointMap };
			addToast(`Checkpoint "${cp.name}" created`, 'success');
			checkpointTarget = null;
			cpName = ''; cpDesc = '';
		} catch (e: any) {
			addToast(e.message ?? 'Failed to create checkpoint', 'error');
		} finally {
			creatingCp = false;
		}
	}

	async function handleRestore() {
		if (!restoreTarget || !$activeRP) return;
		try {
			const res = await restoreCheckpoint(restoreTarget.branch, $activeRP.rp_folder, restoreTarget.checkpoint);
			addToast(`Restored to "${restoreTarget.checkpoint}" (exchange ${res.exchange_number})`, 'success');
			restoreTarget = null;
			await Promise.all([loadBranches(), loadExchanges(true)]);
		} catch (e: any) {
			addToast(e.message ?? 'Failed to restore', 'error');
		}
	}

	// ── Helpers ───────────────────────────────────────────────
	$: filteredExchanges = searchQuery.trim()
		? exchanges.filter(e =>
			e.user_message.toLowerCase().includes(searchQuery.toLowerCase()) ||
			e.assistant_response.toLowerCase().includes(searchQuery.toLowerCase())
		)
		: exchanges;

	function fmt(iso: string) {
		return new Date(iso).toLocaleString(undefined, {
			month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
		});
	}

	function truncate(text: string, len = 140) {
		return text.length > len ? text.slice(0, len) + '…' : text;
	}
</script>

<div class="flex gap-4">

	<!-- ── Left: Branch management ──────────────────────────── -->
	<aside class="w-56 shrink-0 space-y-2 self-start">
		<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
			<div class="px-3 py-2.5 border-b border-border-custom flex items-center justify-between">
				<span class="text-xs font-semibold text-text-dim uppercase tracking-wider">Branches</span>
				<button
					class="text-xs text-accent hover:text-accent-hover transition-colors"
					on:click={() => (showCreate = !showCreate)}
				>
					{showCreate ? 'Cancel' : '+ New'}
				</button>
			</div>

			{#if loadingBranches}
				<div class="px-3 py-4 text-xs text-text-dim">Loading...</div>
			{:else}
				<div class="divide-y divide-border-custom">
					{#each branches as branch}
						<div>
							<!-- Branch row -->
							<div class="flex items-center gap-1.5 px-3 py-2.5 hover:bg-surface2 transition-colors group">
								<button
									class="flex-1 flex items-center gap-1.5 text-left min-w-0"
									on:click={() => handleSwitchBranch(branch)}
									title={branch.is_active ? 'Active branch' : 'Switch to this branch'}
								>
									<span class="w-1.5 h-1.5 rounded-full shrink-0 {branch.is_active ? 'bg-success' : 'bg-border-custom'}"></span>
									<span class="text-sm truncate {branch.is_active ? 'text-text font-medium' : 'text-text-dim'}">
										{branch.name}
									</span>
								</button>
								<span class="text-xs text-text-dim shrink-0">{branch.exchange_count}</span>
								<button
									class="text-text-dim hover:text-text transition-colors opacity-0 group-hover:opacity-100 shrink-0"
									on:click={() => handleExpandBranch(branch.name)}
									title="Checkpoints"
								>
									<svg class="w-3.5 h-3.5 transition-transform {expandedBranch === branch.name ? 'rotate-90' : ''}"
										viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
										<path d="M6 4l4 4-4 4" />
									</svg>
								</button>
							</div>

							<!-- Checkpoints (expanded) -->
							{#if expandedBranch === branch.name}
								<div class="bg-surface2/50 border-t border-border-custom px-3 py-2 space-y-1">
									{#if checkpointMap[branch.name]?.length > 0}
										{#each checkpointMap[branch.name] as cp}
											<div class="flex items-center gap-1.5 text-xs py-0.5 group/cp">
												<span class="text-text-dim">◆</span>
												<span class="text-text flex-1 truncate" title={cp.description ?? cp.name}>{cp.name}</span>
												<span class="text-text-dim shrink-0">#{cp.exchange_number}</span>
												<button
													class="text-warning hover:text-warning/80 opacity-0 group-hover/cp:opacity-100 transition-all shrink-0 text-xs"
													on:click={() => (restoreTarget = { branch: branch.name, checkpoint: cp.name })}
													title="Restore to this checkpoint"
												>↩</button>
											</div>
										{/each}
									{:else}
										<p class="text-xs text-text-dim/60">No checkpoints</p>
									{/if}

									<!-- Add checkpoint -->
									{#if checkpointTarget === branch.name}
										<div class="pt-1 space-y-1.5">
											<input type="text" bind:value={cpName} placeholder="Checkpoint name"
												class="w-full bg-surface border border-border-custom rounded px-2 py-1 text-xs text-text
													focus:outline-none focus:ring-1 focus:ring-accent" />
											<input type="text" bind:value={cpDesc} placeholder="Description (optional)"
												class="w-full bg-surface border border-border-custom rounded px-2 py-1 text-xs text-text
													focus:outline-none focus:ring-1 focus:ring-accent" />
											<div class="flex gap-1.5">
												<button
													class="flex-1 bg-accent text-white text-xs py-1 rounded disabled:opacity-50"
													on:click={() => handleCreateCheckpoint(branch.name)}
													disabled={creatingCp || !cpName.trim()}
												>{creatingCp ? '…' : 'Save'}</button>
												<button
													class="text-xs text-text-dim hover:text-text px-2 py-1"
													on:click={() => { checkpointTarget = null; cpName = ''; cpDesc = ''; }}
												>Cancel</button>
											</div>
										</div>
									{:else}
										<button
											class="text-xs text-accent hover:text-accent-hover transition-colors mt-0.5"
											on:click={() => { checkpointTarget = branch.name; cpName = ''; cpDesc = ''; }}
										>+ Add checkpoint</button>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Create branch form -->
		{#if showCreate}
			<div class="bg-surface rounded-lg border border-border-custom p-3 space-y-2">
				<p class="text-xs font-semibold text-text-dim uppercase tracking-wider">New Branch</p>
				<input type="text" bind:value={newName} placeholder="Branch name"
					class="w-full bg-surface2 border border-border-custom rounded px-2 py-1.5 text-sm text-text
						focus:outline-none focus:ring-1 focus:ring-accent" />
				<input type="text" bind:value={newDesc} placeholder="Description (optional)"
					class="w-full bg-surface2 border border-border-custom rounded px-2 py-1.5 text-sm text-text
						focus:outline-none focus:ring-1 focus:ring-accent" />
				<select bind:value={newFrom}
					class="w-full bg-surface2 border border-border-custom rounded px-2 py-1.5 text-sm text-text
						focus:outline-none focus:ring-1 focus:ring-accent">
					<option value="">Branch from: current</option>
					{#each branches as b}
						<option value={b.name}>{b.name}</option>
					{/each}
				</select>
				<button
					class="w-full bg-accent hover:bg-accent-hover text-white text-sm font-medium py-1.5 rounded
						disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					on:click={handleCreateBranch}
					disabled={creating || !newName.trim()}
				>{creating ? 'Creating…' : 'Create Branch'}</button>
			</div>
		{/if}
	</aside>

	<!-- ── Right: Exchange browser ───────────────────────────── -->
	<div class="flex-1 min-w-0 space-y-3">

		<!-- Search bar -->
		<div class="flex items-center gap-2">
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search exchanges..."
				class="flex-1 bg-surface border border-border-custom rounded-lg px-3 py-2 text-sm text-text
					placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
			/>
			{#if searchQuery}
				<span class="text-xs text-text-dim shrink-0">{filteredExchanges.length} result{filteredExchanges.length !== 1 ? 's' : ''}</span>
				<button class="text-xs text-text-dim hover:text-text transition-colors" on:click={() => (searchQuery = '')}>Clear</button>
			{:else}
				<span class="text-xs text-text-dim shrink-0">{totalExchanges} exchange{totalExchanges !== 1 ? 's' : ''}</span>
			{/if}
		</div>

		<!-- Exchange list -->
		{#if loadingExchanges && exchanges.length === 0}
			<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
				Loading exchanges...
			</div>
		{:else if filteredExchanges.length === 0}
			<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
				{searchQuery ? 'No exchanges match your search.' : 'No exchanges yet on this branch.'}
			</div>
		{:else}
			<div class="space-y-1.5">
				{#each filteredExchanges as exchange}
					<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
						<!-- Exchange header (always visible) -->
						<button
							class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface2 transition-colors text-left"
							on:click={() => (expandedExchangeId = expandedExchangeId === exchange.id ? null : exchange.id)}
						>
							<span class="text-xs font-mono text-text-dim shrink-0 w-10">#{exchange.exchange_number}</span>
							<span class="text-xs text-text-dim shrink-0">{fmt(exchange.created_at)}</span>
							{#if exchange.location}
								<span class="text-xs bg-surface2 text-text-dim px-1.5 py-0.5 rounded shrink-0">{exchange.location}</span>
							{/if}
							{#if exchange.npcs_involved?.length}
								<div class="flex gap-1 flex-wrap flex-1 min-w-0">
									{#each exchange.npcs_involved as npc}
										<span class="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{npc}</span>
									{/each}
								</div>
							{:else}
								<span class="flex-1 min-w-0 text-xs text-text-dim truncate">{truncate(exchange.user_message)}</span>
							{/if}
							<svg class="w-3.5 h-3.5 text-text-dim shrink-0 transition-transform {expandedExchangeId === exchange.id ? 'rotate-180' : ''}"
								viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M4 6l4 4 4-4" />
							</svg>
						</button>

						<!-- Expanded exchange content -->
						{#if expandedExchangeId === exchange.id}
							<div class="border-t border-border-custom divide-y divide-border-custom">
								<!-- User message -->
								<div class="px-4 py-3 space-y-1">
									<p class="text-xs font-medium text-text-dim uppercase tracking-wider">User</p>
									<p class="text-sm text-text whitespace-pre-wrap">{exchange.user_message}</p>
								</div>
								<!-- Assistant response -->
								<div class="px-4 py-3 space-y-1">
									<p class="text-xs font-medium text-text-dim uppercase tracking-wider">Assistant</p>
									<p class="text-sm text-text whitespace-pre-wrap">{exchange.assistant_response}</p>
								</div>
								<!-- Metadata row -->
								{#if exchange.in_story_timestamp || exchange.analysis_status}
									<div class="px-4 py-2 flex items-center gap-3 text-xs text-text-dim bg-surface2/50">
										{#if exchange.in_story_timestamp}
											<span>Story time: {exchange.in_story_timestamp}</span>
										{/if}
										{#if exchange.analysis_status}
											<span class="ml-auto">Analysis: {exchange.analysis_status}</span>
										{/if}
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>

			<!-- Load more -->
			{#if !searchQuery && exchangeOffset < totalExchanges}
				<button
					class="w-full py-2 text-sm text-text-dim hover:text-text hover:bg-surface2 rounded-lg
						border border-border-custom transition-colors disabled:opacity-50"
					on:click={() => loadExchanges(false)}
					disabled={loadingExchanges}
				>
					{loadingExchanges ? 'Loading…' : `Load more (${totalExchanges - exchangeOffset} remaining)`}
				</button>
			{/if}
		{/if}
	</div>
</div>

<!-- ── Restore confirmation overlay ─────────────────────── -->
{#if restoreTarget}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
		<div class="bg-surface border border-border-custom rounded-lg p-6 max-w-sm w-full mx-4 space-y-4">
			<h3 class="text-base font-semibold text-text">Restore checkpoint?</h3>
			<p class="text-sm text-text-dim">
				This will restore branch <span class="text-text font-medium">"{restoreTarget.branch}"</span>
				to checkpoint <span class="text-text font-medium">"{restoreTarget.checkpoint}"</span>.
				Exchanges after that point will be rewound.
			</p>
			<div class="flex gap-3">
				<button
					class="flex-1 bg-error hover:bg-error/80 text-white text-sm font-medium py-2 rounded-md transition-colors"
					on:click={handleRestore}
				>Restore</button>
				<button
					class="flex-1 bg-surface2 hover:bg-surface text-text text-sm py-2 rounded-md border border-border-custom transition-colors"
					on:click={() => (restoreTarget = null)}
				>Cancel</button>
			</div>
		</div>
	</div>
{/if}
