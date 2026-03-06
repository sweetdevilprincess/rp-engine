<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { listCards, getCard, reindex, auditCards, getConnections } from '$lib/api/cards';
	import { getFullState } from '$lib/api/state';
	import { listNPCs } from '$lib/api/npc';
	import { addToast } from '$lib/stores/ui';
	import { CARD_TYPES } from '$lib/types/enums';
	import type { StoryCardSummary, StoryCardDetail, CardListResponse, AuditResponse, AuditGap, GraphData, GraphNode, GraphEdge } from '$lib/types';
	import type { StateSnapshot, CharacterDetail, RelationshipDetail, EventDetail } from '$lib/types';
	import type { NPCListItem } from '$lib/types';
	import ForceGraph from '$lib/components/ForceGraph.svelte';
	import { cardTypeColor, importanceColor, trustStageColor, significanceColor, cardTypeHex, GRAPH_FILTER_TYPES } from '$lib/utils/colors';
	import { cardTypeColors, importanceColors, trustStageColors, significanceColors } from '$lib/utils/colors';
	import Badge from '$lib/components/ui/Badge.svelte';
	import InputField from '$lib/components/ui/InputField.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';
	import SideNav from '$lib/components/ui/SideNav.svelte';
	import SelectField from '$lib/components/ui/SelectField.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import InfoRow from '$lib/components/ui/InfoRow.svelte';
	import EntityChip from '$lib/components/ui/EntityChip.svelte';
	import CardSection from '$lib/components/ui/CardSection.svelte';
	import NPCTrustList from '$lib/components/ui/NPCTrustList.svelte';
	import BackButton from '$lib/components/ui/BackButton.svelte';
	import RPSettings from '$lib/components/RPSettings.svelte';
	import { barStyle } from '$lib/utils/format';

	// ── Tool nav ──
	type ToolId = 'library' | 'state' | 'trust' | 'graph' | 'settings';
	const tools: { id: ToolId; label: string }[] = [
		{ id: 'library',  label: 'Library' },
		{ id: 'state',    label: 'State' },
		{ id: 'trust',    label: 'Trust' },
		{ id: 'graph',    label: 'Graph' },
		{ id: 'settings', label: 'Settings' },
	];
	let activeTool = $state<ToolId>('library');
	let loadedTools = $state(new Set<string>());

	// ── Stats bar ──
	let cardCount = $state(0);
	let connectionCount = $state(0);
	let orphanCount = $state(0);
	let reindexing = $state(false);

	// ── Library tool ──
	let cards = $state<StoryCardSummary[]>([]);
	let librarySearch = $state('');
	let libraryTypeFilter = $state('');
	let selectedCard = $state<StoryCardDetail | null>(null);
	let loadingCard = $state(false);
	let libraryTab = $state<'detail' | 'gaps'>('detail');
	let auditResult = $state<AuditResponse | null>(null);
	let auditing = $state(false);

	// ── State tool ──
	let stateSnapshot = $state<StateSnapshot | null>(null);
	let showAllEvents = $state(false);

	// ── Trust tool ──
	let npcs = $state<NPCListItem[]>([]);
	let trustLoading = $state(false);

	// ── Graph tool ──
	let graphData = $state<GraphData | null>(null);
	let graphFilter = $state('');
	let graphHiddenTypes = $state(new Set<string>());
	let graphFiltersOpen = $state(true);
	let graphSelectedNode = $state<GraphNode | null>(null);
	let graphSelectedCard = $state<StoryCardDetail | null>(null);
	let loadingGraphCard = $state(false);

	let graphFilteredData = $derived.by((): GraphData | null => {
		if (!graphData) return null;
		if (graphHiddenTypes.size === 0) return graphData;
		const nodes = graphData.nodes.filter((n: GraphNode) => !graphHiddenTypes.has(n.card_type));
		const nodeNames = new Set(nodes.map((n: GraphNode) => n.name));
		const edges = graphData.edges.filter((e: GraphEdge) => nodeNames.has(e.from) && nodeNames.has(e.to));
		return { nodes, edges };
	});

	function toggleGraphType(type: string) {
		if (graphHiddenTypes.has(type)) {
			graphHiddenTypes.delete(type);
		} else {
			graphHiddenTypes.add(type);
		}
		graphHiddenTypes = new Set(graphHiddenTypes); // trigger reactivity
	}

	async function handleGraphNodeClick(node: GraphNode) {
		graphSelectedNode = node;
		loadingGraphCard = true;
		try {
			graphSelectedCard = await getCard(node.card_type, node.name);
		} catch {
			graphSelectedCard = null;
		} finally {
			loadingGraphCard = false;
		}
	}

	let rpFolder = $derived($page.params.rp ?? '');

	// ── Deep-link support ──
	let pendingExpandNpc = $state<string | null>(null);

	// ── Init ──
	onMount(async () => {
		// Check for deep-link query params
		const toolParam = $page.url.searchParams.get('tool');
		const npcParam = $page.url.searchParams.get('npc');
		if (npcParam) pendingExpandNpc = npcParam;

		await loadStats();

		if (toolParam && tools.some(t => t.id === toolParam)) {
			await switchTool(toolParam as ToolId);
		} else {
			await loadTool('library');
		}

		// NPCTrustList handles auto-expand via initialExpand prop
	});

	async function loadStats() {
		try {
			const res: CardListResponse = await listCards();
			cards = res.cards;
			cardCount = res.total;
			connectionCount = Math.floor(cards.reduce((sum, c) => sum + c.connection_count, 0) / 2);
			orphanCount = cards.filter(c => c.connection_count === 0).length;
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load cards', 'error');
		}
	}

	async function loadTool(tool: ToolId) {
		if (loadedTools.has(tool)) return;
		try {
			if (tool === 'library') {
				// cards already loaded in loadStats
			} else if (tool === 'state') {
				stateSnapshot = await getFullState();
			} else if (tool === 'trust') {
				trustLoading = true;
				npcs = await listNPCs();
				trustLoading = false;
			} else if (tool === 'graph') {
				graphData = await getConnections();
			}
			loadedTools.add(tool);
			loadedTools = loadedTools; // trigger reactivity
		} catch (e: any) {
			addToast(e.message ?? `Failed to load ${tool}`, 'error');
			if (tool === 'trust') trustLoading = false;
		}
	}

	function switchTool(tool: ToolId) {
		activeTool = tool;
		loadTool(tool);
	}

	async function handleReindex() {
		reindexing = true;
		try {
			const res = await reindex();
			addToast(`Reindexed: ${res.entities} entities, ${res.connections} connections (${res.duration_ms}ms)`, 'success');
			// Reset loaded tools so they refetch
			loadedTools = new Set<string>();
			await loadStats();
			await loadTool(activeTool);
		} catch (e: any) {
			addToast(e.message ?? 'Reindex failed', 'error');
		} finally {
			reindexing = false;
		}
	}

	// ── Library helpers ──
	async function selectCard(card: StoryCardSummary) {
		loadingCard = true;
		libraryTab = 'detail';
		try {
			selectedCard = await getCard(card.card_type, card.name);
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load card', 'error');
		} finally {
			loadingCard = false;
		}
	}

	async function selectCardByName(name: string) {
		const match = cards.find(c => c.name === name);
		if (match) await selectCard(match);
	}

	async function runAudit() {
		auditing = true;
		try {
			auditResult = await auditCards('quick');
		} catch (e: any) {
			addToast(e.message ?? 'Audit failed', 'error');
		} finally {
			auditing = false;
		}
	}

	let filteredCards = $derived(
		cards
			.filter(c => {
				if (libraryTypeFilter && c.card_type !== libraryTypeFilter) return false;
				if (librarySearch.trim()) {
					const q = librarySearch.toLowerCase();
					return c.name.toLowerCase().includes(q) || c.card_type.toLowerCase().includes(q) ||
						(c.summary ?? '').toLowerCase().includes(q);
				}
				return true;
			})
			.sort((a, b) => b.connection_count - a.connection_count || a.name.localeCompare(b.name))
	);

	// ── State helpers ──
	let playerChars = $derived.by(() => {
		if (!stateSnapshot) return [] as [string, CharacterDetail][];
		return Object.entries(stateSnapshot.characters).filter(([, c]) => c.is_player_character);
	});
	let npcChars = $derived.by(() => {
		if (!stateSnapshot) return [] as [string, CharacterDetail][];
		return Object.entries(stateSnapshot.characters).filter(([, c]) => !c.is_player_character);
	});
	let sortedEvents = $derived.by(() => {
		if (!stateSnapshot) return [] as EventDetail[];
		return [...stateSnapshot.events].sort((a, b) => b.id - a.id);
	});
	let visibleEvents = $derived(showAllEvents ? sortedEvents : sortedEvents.slice(0, 50));


</script>

<!-- Stats bar -->
<div class="flex items-center justify-between bg-surface border border-border-custom rounded-[10px] px-4 py-2.5 mb-3">
	<div class="flex items-center gap-3.5 text-[13px]">
		<span><strong>{cardCount}</strong> <span class="text-text-dim">cards</span></span>
		<span class="text-text-dim/60">·</span>
		<span><strong>{connectionCount}</strong> <span class="text-text-dim">connections</span></span>
		<span class="text-text-dim/60">·</span>
		<span class="{orphanCount > 0 ? 'text-warning' : ''}"><strong>{orphanCount}</strong> <span class="text-text-dim">orphans</span></span>
	</div>
	<button
		class="px-3 py-1.5 text-xs rounded-lg border border-border-custom bg-surface text-text-dim hover:text-text hover:border-border-custom transition-colors disabled:opacity-50"
		onclick={handleReindex}
		disabled={reindexing}
	>
		{reindexing ? 'Reindexing...' : 'Reindex'}
	</button>
</div>

<!-- Main layout: nav + content -->
<div class="flex gap-3">
	<SideNav title="Dashboard" items={tools} bind:active={activeTool} onselect={(id) => switchTool(id as ToolId)} />

	<!-- Tool content -->
	<div class="flex-1 min-w-0">

		<!-- ═══════════ LIBRARY ═══════════ -->
		{#if activeTool === 'library'}
			{#if selectedCard}
				<!-- Detail view (replaces grid when a card is selected) -->
				<div class="bg-surface border border-border-custom rounded-lg overflow-hidden">
					<div class="flex items-center gap-2 px-4 py-2.5 border-b border-border-custom">
						<BackButton label="Back to library" onclick={() => (selectedCard = null)} />
					</div>
					<div class="p-4 space-y-4">
						<!-- Header -->
						<div class="flex items-center gap-2">
							<Badge color={cardTypeColors(selectedCard.card_type).text} bg={cardTypeColors(selectedCard.card_type).bg} dot={cardTypeColors(selectedCard.card_type).hex}>{selectedCard.card_type.replaceAll('_', ' ')}</Badge>
							<h3 class="text-base font-semibold text-text font-serif">{selectedCard.name}</h3>
							{#if selectedCard.importance}
								{@const imp = importanceColors(selectedCard.importance)}
								<Badge color={imp.text} bg={imp.bg}>{selectedCard.importance}</Badge>
							{/if}
						</div>

						<!-- Content summary -->
						{#if selectedCard.content}
							<div class="text-sm text-text-dim leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
								{selectedCard.content.slice(0, 800)}{selectedCard.content.length > 800 ? '...' : ''}
							</div>
						{/if}

						<!-- Frontmatter -->
						{#if Object.keys(selectedCard.frontmatter).length > 0}
							<div>
								<div class="mb-2"><SectionLabel>Frontmatter</SectionLabel></div>
								<div class="grid grid-cols-2 gap-x-4 gap-y-1">
									{#each Object.entries(selectedCard.frontmatter) as [key, val]}
										<div class="flex gap-2 text-xs py-0.5">
											<span class="text-text-dim shrink-0">{key}</span>
											<span class="text-text truncate">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						<!-- Connections -->
						{#if selectedCard.connections.length > 0}
							<div>
								<div class="mb-2"><SectionLabel>Connections ({selectedCard.connections.length})</SectionLabel></div>
								<div class="flex flex-wrap gap-1.5">
									{#each selectedCard.connections as conn}
										<EntityChip label={conn.connection_type} name={conn.to_entity} variant="subtle" onclick={() => selectCardByName(conn.to_entity)} />
									{/each}
								</div>
							</div>
						{:else}
							<p class="text-xs text-warning">No connections (orphan card)</p>
						{/if}
					</div>
				</div>
			{:else}
				<!-- Grid view -->
				<div class="space-y-3">
					<!-- Filter controls -->
					<div class="flex items-center gap-2">
						<div class="flex-1 min-w-0">
							<InputField bind:value={librarySearch} placeholder="Search cards..." />
						</div>
						<div class="shrink-0">
							<SelectField bind:value={libraryTypeFilter} placeholder="All types"
								options={CARD_TYPES.map(ct => ({value: ct, label: ct}))} />
						</div>
						<button
							class="px-3 py-2 text-xs rounded-lg bg-accent/20 text-accent hover:bg-accent/30 transition-colors disabled:opacity-50"
							onclick={runAudit}
							disabled={auditing}
						>
							{auditing ? 'Auditing...' : 'Run Audit'}
						</button>
						<span class="text-xs text-text-dim shrink-0">{filteredCards.length} / {cards.length}</span>
					</div>

					<!-- Audit results (inline if available) -->
					{#if auditResult && auditResult.gaps.length > 0}
						<div class="bg-warning/5 border border-warning/20 rounded-lg px-4 py-3">
							<p class="text-xs font-semibold text-warning mb-2">
								{auditResult.total_gaps} gap{auditResult.total_gaps !== 1 ? 's' : ''} found
								<span class="text-text-dim font-normal">({auditResult.total_exchanges_scanned} exchanges scanned)</span>
							</p>
							<div class="flex flex-wrap gap-1.5">
								{#each auditResult.gaps.slice(0, 8) as gap}
									<span class="text-xs bg-surface px-2 py-1 rounded-lg border border-border-custom">
										{gap.entity_name}
										{#if gap.suggested_type}
											<span class="text-text-dim">({gap.suggested_type})</span>
										{/if}
										<span class="text-text-dim font-mono">{gap.mention_count}x</span>
									</span>
								{/each}
								{#if auditResult.gaps.length > 8}
									<span class="text-xs text-text-dim self-center">+{auditResult.gaps.length - 8} more</span>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Card grid -->
					{#if filteredCards.length === 0}
						<EmptyState message="No cards match your filters." />
					{:else}
						<div class="grid grid-cols-3 gap-2">
							{#each filteredCards as card}
								{@const cs = cardTypeColors(card.card_type)}
								<button
									class="bg-surface rounded-[10px] border border-border-custom p-3 px-3.5 text-left
										hover:border-accent/25 hover:shadow-sm transition-all"
									onclick={() => selectCard(card)}
								>
									<div class="flex items-center gap-1.5 mb-1.5">
										<span class="w-1.5 h-1.5 rounded-full shrink-0" style="background: {cs.hex}"></span>
										<span class="font-serif text-[13px] font-medium text-text truncate">{card.name}</span>
									</div>
									<div class="flex gap-1 flex-wrap mb-1.5">
										<Badge color={cs.text} bg={cs.bg}>{card.card_type.replaceAll('_', ' ')}</Badge>
										{#if card.importance}
											{@const imp = importanceColors(card.importance)}
											<Badge color={imp.text} bg={imp.bg}>{card.importance}</Badge>
										{/if}
									</div>
									{#if card.summary}
										<p class="text-xs text-text-dim leading-snug line-clamp-2 m-0">{card.summary}</p>
									{/if}
								</button>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

		<!-- ═══════════ STATE ═══════════ -->
		{:else if activeTool === 'state'}
			{#if !stateSnapshot}
				<EmptyState message="Loading state..." variant="loading" />
			{:else}
				<div class="grid grid-cols-2 gap-3">
					<!-- Scene card -->
					<CardSection title="Scene" compact>
						<div class="px-4 py-3 flex flex-col gap-[5px]">
							{#each [['Location', stateSnapshot.scene.location], ['Time of Day', stateSnapshot.scene.time_of_day], ['Mood', stateSnapshot.scene.mood], ['Timestamp', stateSnapshot.scene.in_story_timestamp]] as [label, val]}
								{#if val}
									<InfoRow label={label ?? ''} value={val} />
								{/if}
							{/each}
							{#if !stateSnapshot.scene.location && !stateSnapshot.scene.time_of_day && !stateSnapshot.scene.mood}
								<div class="text-xs text-text-dim">No scene data yet.</div>
							{/if}
						</div>
					</CardSection>

					<!-- Characters card -->
					<CardSection title="Characters" compact>
						<div class="px-4 py-3 flex flex-col gap-2">
							{#each [...playerChars, ...npcChars] as entry}
								{@const name = entry[0]}
								{@const char = entry[1]}
								<div class="text-[13px]">
									<span class="font-medium">{name}</span>
									{#if char.emotional_state}
										<span class="text-text-dim italic text-xs font-serif ml-1">{char.emotional_state}</span>
									{/if}
									{#if char.conditions.length > 0}
										<div class="flex gap-1 mt-0.5">
											{#each char.conditions as cond}
												<Badge>{cond}</Badge>
											{/each}
										</div>
									{/if}
								</div>
							{/each}
							{#if playerChars.length === 0 && npcChars.length === 0}
								<div class="text-xs text-text-dim">No character data yet.</div>
							{/if}
						</div>
					</CardSection>
				</div>

				<!-- Events (below, full width) -->
				{#if sortedEvents.length > 0}
					<div class="mt-3">
					<CardSection title="Recent Events" compact>
						<div class="p-3 space-y-1">
							{#each visibleEvents as evt}
								<div class="flex items-start gap-2 text-xs py-1.5 border-b border-border-custom/50">
									<span class="text-text-dim shrink-0 w-20 truncate">{evt.in_story_timestamp ?? '—'}</span>
									<span class="text-text flex-1">{evt.event}</span>
									{#if evt.significance}
										<span class="px-1 py-0.5 rounded text-[10px] shrink-0" style="{significanceColor(evt.significance)}">{evt.significance}</span>
									{/if}
									<div class="flex gap-0.5 shrink-0">
										{#each evt.characters as ch}
											<span class="bg-surface2 px-1 py-0.5 rounded text-[10px] text-text-dim">{ch}</span>
										{/each}
									</div>
								</div>
							{/each}
							{#if !showAllEvents && sortedEvents.length > 50}
								<button
									class="text-xs text-accent hover:underline"
									onclick={() => (showAllEvents = true)}
								>Show all {sortedEvents.length} events</button>
							{/if}
						</div>
					</CardSection>
					</div>
				{/if}

				<!-- Relationships (below, full width) -->
				{#if stateSnapshot.relationships.length > 0}
					<div class="mt-3">
					<CardSection title="Relationships" compact>
						<div class="p-3 overflow-x-auto">
							<table class="w-full text-xs">
								<thead>
									<tr class="text-text-dim text-left border-b border-border-custom">
										<th class="pb-1 pr-3">Character A</th>
										<th class="pb-1 pr-3">Character B</th>
										<th class="pb-1 pr-3">Trust</th>
										<th class="pb-1">Stage</th>
									</tr>
								</thead>
								<tbody>
									{#each stateSnapshot.relationships as rel}
										<tr class="border-b border-border-custom/30">
											<td class="py-1 pr-3 text-text">{rel.character_a}</td>
											<td class="py-1 pr-3 text-text">{rel.character_b}</td>
											<td class="py-1 pr-3 font-mono {rel.live_trust_score > 0 ? 'text-success' : rel.live_trust_score < 0 ? 'text-error' : 'text-text-dim'}">
												{rel.live_trust_score > 0 ? '+' : ''}{rel.live_trust_score}
											</td>
											<td class="py-1">
												<span class="px-1 py-0.5 rounded text-[10px]" style="{trustStageColor(rel.trust_stage)}">{rel.trust_stage}</span>
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</CardSection>
					</div>
				{/if}
			{/if}

		<!-- ═══════════ TRUST ═══════════ -->
		{:else if activeTool === 'trust'}
			<NPCTrustList {npcs} loading={trustLoading} initialExpand={pendingExpandNpc} />

		<!-- ═══════════ GRAPH ═══════════ -->
		<!-- ═══════════ SETTINGS ═══════════ -->
		{:else if activeTool === 'settings'}
			<RPSettings {rpFolder} />

		<!-- ═══════════ GRAPH ═══════════ -->
		{:else if activeTool === 'graph'}
			<div class="relative bg-surface border border-border-custom rounded-[10px] overflow-hidden flex flex-col" style="height: calc(100vh - 180px)">

				<!-- Graph canvas (full area) -->
				<div class="flex-1 min-h-0">
					{#if !graphFilteredData}
						<div class="flex items-center justify-center h-full text-xs text-text-dim">Loading graph data...</div>
					{:else}
						{#key [...graphHiddenTypes].sort().join(',')}
						<ForceGraph data={graphFilteredData} filter={graphFilter} onNodeClick={handleGraphNodeClick} />
					{/key}
					{/if}
				</div>

				<!-- Floating filter panel (top-right) -->
				<div class="absolute top-3 right-3 z-10">
					{#if graphFiltersOpen}
						<div class="bg-surface/95 backdrop-blur-sm border border-border-custom rounded-lg shadow-lg w-64">
							<div class="flex items-center justify-between px-3 py-2 border-b border-border-custom">
								<SectionLabel>Filters</SectionLabel>
								<button
									class="text-xs text-text-dim hover:text-text transition-colors"
									onclick={() => (graphFiltersOpen = false)}
								>Hide</button>
							</div>
							<div class="p-3 space-y-3">
								<input
									type="text"
									bind:value={graphFilter}
									placeholder="Search nodes..."
									class="w-full bg-bg-subtle border border-border-custom rounded px-2 py-1.5 text-xs text-text
										placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
								/>
								{#if graphData}
									<p class="text-[10px] text-text-dim">{graphData.nodes.length} nodes · {graphData.edges.length} edges</p>
									<div class="flex flex-wrap gap-1">
										{#each GRAPH_FILTER_TYPES.map(t => [t, cardTypeHex(t)]) as [type, color]}
											<button
												class="flex items-center gap-1 shrink-0 px-2 py-1 rounded-full transition-all border text-[10px]
													{graphHiddenTypes.has(type)
														? 'opacity-30 border-transparent text-text-dim'
														: 'border-border-custom/50 text-text-dim hover:text-text'}"
												onclick={() => toggleGraphType(type)}
												title="{graphHiddenTypes.has(type) ? 'Show' : 'Hide'} {type} nodes"
											>
												<span class="w-2 h-2 rounded-full" style="background:{color}"></span>
												{type}
											</button>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					{:else}
						<button
							class="bg-surface/95 backdrop-blur-sm border border-border-custom rounded-lg shadow-lg px-3 py-2 text-xs text-text-dim hover:text-text transition-colors"
							onclick={() => (graphFiltersOpen = true)}
						>Filters</button>
					{/if}
				</div>

				<!-- Floating card preview (top-left, on node click) -->
				{#if graphSelectedNode}
					<div class="absolute top-3 left-3 z-10 bg-surface/95 backdrop-blur-sm border border-border-custom rounded-[10px] shadow-lg w-72 max-h-[60%] overflow-y-auto">
						<div class="flex items-center justify-between px-3 py-2 border-b border-border-custom">
							<div class="flex items-center gap-2 min-w-0">
								<span class="px-1.5 py-0.5 rounded text-[10px] leading-none" style="{cardTypeColor(graphSelectedNode.card_type)}">{graphSelectedNode.card_type}</span>
								<span class="text-xs font-medium text-text truncate">{graphSelectedNode.name}</span>
							</div>
							<button
								class="text-xs text-text-dim hover:text-text transition-colors shrink-0 ml-2"
								onclick={() => { graphSelectedNode = null; graphSelectedCard = null; }}
							>Close</button>
						</div>
						<div class="p-3">
							{#if loadingGraphCard}
								<p class="text-xs text-text-dim">Loading...</p>
							{:else if graphSelectedCard}
								{#if graphSelectedCard.importance}
									<span class="text-[10px] px-1.5 py-0.5 rounded" style="{importanceColor(graphSelectedCard.importance)}">{graphSelectedCard.importance}</span>
								{/if}
								{#if graphSelectedCard.content}
									<p class="text-xs text-text-dim mt-2 leading-relaxed whitespace-pre-wrap">{graphSelectedCard.content.slice(0, 400)}{graphSelectedCard.content.length > 400 ? '...' : ''}</p>
								{/if}
								{#if graphSelectedCard.connections.length > 0}
									<div class="mt-3">
										<p class="text-[10px] text-text-dim uppercase tracking-wider mb-1">Connections ({graphSelectedCard.connections.length})</p>
										<div class="flex flex-wrap gap-1">
											{#each graphSelectedCard.connections.slice(0, 8) as conn}
												<span class="text-[10px] bg-bg-subtle text-text-dim px-1.5 py-0.5 rounded">{conn.to_entity}</span>
											{/each}
											{#if graphSelectedCard.connections.length > 8}
												<span class="text-[10px] text-text-dim">+{graphSelectedCard.connections.length - 8}</span>
											{/if}
										</div>
									</div>
								{/if}
								<button
									class="mt-3 text-xs text-accent hover:underline"
									onclick={() => { switchTool('library'); selectCardByName(graphSelectedNode?.name ?? ''); graphSelectedNode = null; graphSelectedCard = null; }}
								>View full card</button>
							{:else}
								<p class="text-xs text-text-dim">Card not found.</p>
							{/if}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
