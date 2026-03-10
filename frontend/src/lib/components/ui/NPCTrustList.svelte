<script lang="ts">
	/**
	 * Shared NPC trust list with expandable details and trust history.
	 * Used by both the NPC page and the Dashboard trust tool.
	 */
	import { getTrustInfo } from '$lib/api/npc';
	import { addToast } from '$lib/stores/ui';
	import type { NPCListItem, TrustInfo } from '$lib/types';
	import { importanceColors, trustStageColors, modifierColors } from '$lib/utils/colors';
	import { ARCHETYPE_DESCRIPTIONS, MODIFIER_DESCRIPTIONS } from '$lib/constants/archetypes';
	import Badge from './Badge.svelte';
	import Tooltip from './Tooltip.svelte';
	import TrustBar from './TrustBar.svelte';
	import EmptyState from './EmptyState.svelte';
	import InputField from './InputField.svelte';
	import SelectField from './SelectField.svelte';
	import { formatDate } from '$lib/utils/format';

	interface Props {
		npcs: NPCListItem[];
		loading?: boolean;
		/** NPC name to auto-expand on mount */
		initialExpand?: string | null;
	}

	let { npcs, loading = false, initialExpand = null }: Props = $props();

	let expandedNpc = $state<string | null>(null);
	let trustDetails = $state<Record<string, TrustInfo>>({});
	let loadingTrust = $state<Record<string, boolean>>({});

	let sortBy = $state<'trust_desc' | 'trust_asc' | 'name' | 'importance'>('trust_desc');
	let filterText = $state('');

	// Auto-expand if requested
	$effect(() => {
		if (initialExpand && npcs.length > 0 && !expandedNpc) {
			toggleExpand(initialExpand);
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

	let sorted = $derived(
		[...npcs]
			.filter(n =>
				!filterText.trim() ||
				n.name.toLowerCase().includes(filterText.toLowerCase()) ||
				(n.primary_archetype ?? '').toLowerCase().includes(filterText.toLowerCase())
			)
			.sort((a, b) => {
				if (sortBy === 'trust_desc') return b.trust_score - a.trust_score;
				if (sortBy === 'trust_asc') return a.trust_score - b.trust_score;
				if (sortBy === 'name') return a.name.localeCompare(b.name);
				if (sortBy === 'importance') {
					const rank = (i: string | null) => i === 'primary' ? 0 : i === 'secondary' ? 1 : 2;
					return rank(a.importance) - rank(b.importance);
				}
				return 0;
			})
	);
</script>

<div class="space-y-4">
	<!-- Controls -->
	<div class="flex items-center gap-3">
		<div class="flex-1 min-w-0">
			<InputField bind:value={filterText} placeholder="Filter by name or archetype..." />
		</div>
		<div class="shrink-0">
			<SelectField bind:value={sortBy} options={[
				{value: 'trust_desc', label: 'Trust: High → Low'},
				{value: 'trust_asc', label: 'Trust: Low → High'},
				{value: 'name', label: 'Name A–Z'},
				{value: 'importance', label: 'Importance'}
			]} />
		</div>
		<span class="text-sm text-text-dim shrink-0">{sorted.length} NPC{sorted.length !== 1 ? 's' : ''}</span>
	</div>

	<!-- NPC list -->
	{#if loading}
		<EmptyState message="Loading NPCs..." variant="loading" />
	{:else if sorted.length === 0}
		<EmptyState message={filterText ? 'No NPCs match your filter.' : 'No NPCs found for this RP.'} />
	{:else}
		<div class="space-y-2">
			{#each sorted as npc}
				<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">

					<!-- NPC summary row -->
					<button
						class="w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-subtle transition-colors text-left"
						onclick={() => toggleExpand(npc.name)}
					>
						<!-- Name -->
						<div class="flex items-center gap-2 w-48 shrink-0 min-w-0">
							<span class="font-medium text-text truncate">{npc.name}</span>
						</div>
						<!-- Badges -->
						<div class="flex items-center gap-1.5 shrink-0">
							{#if npc.importance}
								{@const ic = importanceColors(npc.importance)}
								<Badge color={ic.text} bg={ic.bg}>{npc.importance}</Badge>
							{/if}
							{#if npc.primary_archetype}
								<Tooltip text={ARCHETYPE_DESCRIPTIONS[npc.primary_archetype] ?? npc.primary_archetype}>
									<Badge>{npc.primary_archetype}</Badge>
								</Tooltip>
							{/if}
						</div>

						<!-- Trust bar -->
						<TrustBar score={npc.trust_score} />

						<!-- Trust stage -->
						{#if npc.trust_stage}
							{@const ts = trustStageColors(npc.trust_stage)}
							<Badge color={ts.text} bg={ts.bg}>{npc.trust_stage}</Badge>
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
												{@const mc = modifierColors(mod)}
												<Tooltip text={MODIFIER_DESCRIPTIONS[mod] ?? mod}>
													<Badge color={mc.text} bg={mc.bg}>{mod}</Badge>
												</Tooltip>
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
