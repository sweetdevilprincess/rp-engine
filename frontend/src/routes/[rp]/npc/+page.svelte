<script lang="ts">
	import { onMount } from 'svelte';
	import { listNPCs, getTrustInfo } from '$lib/api/npc';
	import { addToast } from '$lib/stores/ui';
	import type { NPCListItem, TrustInfo } from '$lib/types';

	let npcs: NPCListItem[] = [];
	let loading = false;
	let expandedNpc: string | null = null;
	let trustDetails: Record<string, TrustInfo> = {};
	let loadingTrust: Record<string, boolean> = {};

	// Sort + filter
	let sortBy: 'trust_desc' | 'trust_asc' | 'name' | 'importance' = 'trust_desc';
	let filterText = '';

	onMount(async () => {
		loading = true;
		try {
			npcs = await listNPCs();
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load NPCs', 'error');
		} finally {
			loading = false;
		}
	});

	async function toggleExpand(name: string) {
		if (expandedNpc === name) {
			expandedNpc = null;
			return;
		}
		expandedNpc = name;
		if (!trustDetails[name]) {
			loadingTrust[name] = true;
			try {
				trustDetails[name] = await getTrustInfo(name);
				trustDetails = { ...trustDetails };
			} catch (e: any) {
				addToast(e.message ?? `Failed to load trust for ${name}`, 'error');
			} finally {
				loadingTrust[name] = false;
			}
		}
	}

	// Trust bar: range -100 to +100, center at 50%
	function barStyle(score: number): string {
		const clamped = Math.max(-100, Math.min(100, score));
		const width = Math.abs(clamped) / 2;
		const left = clamped >= 0 ? 50 : 50 + clamped / 2;
		const color = clamped >= 0 ? '#4caf50' : '#ef5350';
		return `left:${left}%;width:${width}%;background:${color}`;
	}

	function trustStageColor(stage: string | null): string {
		if (!stage) return 'bg-surface2 text-text-dim';
		const s = stage.toLowerCase();
		if (s.includes('hostile') || s.includes('enemy')) return 'bg-error/20 text-error';
		if (s.includes('distrust') || s.includes('suspicious')) return 'bg-warning/20 text-warning';
		if (s.includes('neutral')) return 'bg-surface2 text-text-dim';
		if (s.includes('acquaint') || s.includes('friendly')) return 'bg-green-500/20 text-green-400';
		if (s.includes('trust') || s.includes('ally') || s.includes('bond')) return 'bg-accent/20 text-accent';
		return 'bg-surface2 text-text-dim';
	}

	function importanceColor(imp: string | null): string {
		if (!imp) return 'bg-surface2 text-text-dim';
		if (imp === 'primary') return 'bg-accent/20 text-accent';
		if (imp === 'secondary') return 'bg-surface2 text-text';
		return 'bg-surface2 text-text-dim';
	}

	function formatDate(iso: string) {
		return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	$: sorted = [...npcs]
		.filter(n =>
			!filterText.trim() ||
			n.name.toLowerCase().includes(filterText.toLowerCase()) ||
			(n.primary_archetype ?? '').toLowerCase().includes(filterText.toLowerCase())
		)
		.sort((a, b) => {
			if (sortBy === 'trust_desc') return b.trust_score - a.trust_score;
			if (sortBy === 'trust_asc')  return a.trust_score - b.trust_score;
			if (sortBy === 'name')       return a.name.localeCompare(b.name);
			if (sortBy === 'importance') {
				const rank = (i: string | null) => i === 'primary' ? 0 : i === 'secondary' ? 1 : 2;
				return rank(a.importance) - rank(b.importance);
			}
			return 0;
		});
</script>

<div class="space-y-4 max-w-4xl">

	<!-- Controls -->
	<div class="flex items-center gap-3">
		<input
			type="text"
			bind:value={filterText}
			placeholder="Filter by name or archetype..."
			class="flex-1 bg-surface border border-border-custom rounded-lg px-3 py-2 text-sm text-text
				placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
		/>
		<select
			bind:value={sortBy}
			class="bg-surface border border-border-custom rounded-lg px-3 py-2 text-sm text-text
				focus:outline-none focus:ring-1 focus:ring-accent"
		>
			<option value="trust_desc">Trust: High → Low</option>
			<option value="trust_asc">Trust: Low → High</option>
			<option value="name">Name A–Z</option>
			<option value="importance">Importance</option>
		</select>
		<span class="text-sm text-text-dim shrink-0">{sorted.length} NPC{sorted.length !== 1 ? 's' : ''}</span>
	</div>

	<!-- NPC list -->
	{#if loading}
		<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
			Loading NPCs...
		</div>
	{:else if sorted.length === 0}
		<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
			{filterText ? 'No NPCs match your filter.' : 'No NPCs found for this RP.'}
		</div>
	{:else}
		<div class="space-y-2">
			{#each sorted as npc}
				<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">

					<!-- NPC summary row -->
					<button
						class="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface2 transition-colors text-left"
						on:click={() => toggleExpand(npc.name)}
					>
						<!-- Name + badges -->
						<div class="flex items-center gap-2 w-48 shrink-0 min-w-0">
							<span class="font-medium text-text truncate">{npc.name}</span>
						</div>
						<div class="flex items-center gap-1.5 shrink-0">
							{#if npc.importance}
								<span class="text-xs px-1.5 py-0.5 rounded {importanceColor(npc.importance)}">{npc.importance}</span>
							{/if}
							{#if npc.primary_archetype}
								<span class="text-xs px-1.5 py-0.5 rounded bg-surface2 text-text-dim">{npc.primary_archetype}</span>
							{/if}
						</div>

						<!-- Trust bar -->
						<div class="flex-1 flex items-center gap-3 min-w-0">
							<div class="relative flex-1 h-2 bg-surface2 rounded-full overflow-hidden">
								<!-- Center tick -->
								<div class="absolute top-0 bottom-0 w-px bg-border-custom" style="left:50%"></div>
								<!-- Fill -->
								<div class="absolute top-0 bottom-0 rounded-full" style="{barStyle(npc.trust_score)}"></div>
							</div>
							<span class="text-sm font-mono w-10 text-right shrink-0
								{npc.trust_score > 0 ? 'text-success' : npc.trust_score < 0 ? 'text-error' : 'text-text-dim'}">
								{npc.trust_score > 0 ? '+' : ''}{npc.trust_score}
							</span>
						</div>

						<!-- Trust stage -->
						{#if npc.trust_stage}
							<span class="text-xs px-2 py-0.5 rounded {trustStageColor(npc.trust_stage)} shrink-0">
								{npc.trust_stage}
							</span>
						{/if}

						<!-- Expand chevron -->
						<svg class="w-4 h-4 text-text-dim shrink-0 transition-transform {expandedNpc === npc.name ? 'rotate-180' : ''}"
							viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M4 6l4 4 4-4" />
						</svg>
					</button>

					<!-- Expanded details -->
					{#if expandedNpc === npc.name}
						<div class="border-t border-border-custom">

							<!-- State + modifiers -->
							<div class="px-4 py-3 grid grid-cols-2 gap-4 text-sm border-b border-border-custom">
								<div class="space-y-1.5">
									{#if npc.emotional_state}
										<div><span class="text-text-dim text-xs">Emotional state</span><br>
											<span class="text-text">{npc.emotional_state}</span></div>
									{/if}
									{#if npc.location}
										<div><span class="text-text-dim text-xs">Location</span><br>
											<span class="text-text">{npc.location}</span></div>
									{/if}
									{#if npc.secondary_archetype}
										<div><span class="text-text-dim text-xs">Secondary archetype</span><br>
											<span class="text-text">{npc.secondary_archetype}</span></div>
									{/if}
								</div>
								{#if npc.behavioral_modifiers?.length}
									<div>
										<span class="text-text-dim text-xs">Behavioral modifiers</span>
										<div class="flex flex-wrap gap-1 mt-1">
											{#each npc.behavioral_modifiers as mod}
												<span class="text-xs bg-surface2 text-text-dim px-1.5 py-0.5 rounded">{mod}</span>
											{/each}
										</div>
									</div>
								{/if}
							</div>

							<!-- Trust detail (lazy loaded) -->
							{#if loadingTrust[npc.name]}
								<div class="px-4 py-3 text-xs text-text-dim">Loading trust history...</div>
							{:else if trustDetails[npc.name]}
								{@const td = trustDetails[npc.name]}
								<div class="px-4 py-3 space-y-3">
									<!-- Session stats -->
									<div class="flex items-center gap-4 text-sm">
										<span class="text-text-dim text-xs">This session:</span>
										{#if td.session_gains > 0}
											<span class="text-success text-xs">+{td.session_gains} gains</span>
										{/if}
										{#if td.session_losses > 0}
											<span class="text-error text-xs">−{td.session_losses} losses</span>
										{/if}
										{#if td.session_gains === 0 && td.session_losses === 0}
											<span class="text-text-dim text-xs">No changes this session</span>
										{/if}
									</div>

									<!-- Trust history -->
									{#if td.history?.length}
										<div>
											<p class="text-xs text-text-dim mb-2">Recent history</p>
											<div class="space-y-1 max-h-48 overflow-y-auto">
												{#each td.history.slice(-20).reverse() as event}
													<div class="flex items-start gap-2 text-xs py-1 border-b border-border-custom/50 last:border-0">
														<span class="font-mono shrink-0
															{event.direction === 'increase' ? 'text-success' : event.direction === 'decrease' ? 'text-error' : 'text-text-dim'}">
															{event.direction === 'increase' ? '+' : event.direction === 'decrease' ? '−' : '·'}{Math.abs(event.change)}
														</span>
														<span class="text-text-dim shrink-0">{formatDate(event.date)}</span>
														{#if event.reason}
															<span class="text-text flex-1">{event.reason}</span>
														{/if}
													</div>
												{/each}
											</div>
										</div>
									{:else}
										<p class="text-xs text-text-dim">No trust history recorded.</p>
									{/if}
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
