<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { listCards, getCard, reindex, auditCards, getConnections } from '$lib/api/cards';
	import { getFullState, updateScene, updateCharacter, adjustTrust, getRelationshipGraph } from '$lib/api/state';
	import { listNPCs } from '$lib/api/npc';
	import { addToast } from '$lib/stores/ui';
	import { CARD_TYPES } from '$lib/types/enums';
	import type { StoryCardSummary, StoryCardDetail, CardListResponse, AuditResponse, AuditGap, GraphData, GraphNode, GraphEdge } from '$lib/types';
	import type { StateSnapshot, CharacterDetail, RelationshipDetail, EventDetail, RelationshipGraphResponse, RelGraphNode } from '$lib/types';
	import type { NPCListItem } from '$lib/types';
	import ForceGraph from '$lib/components/ForceGraph.svelte';
	import RelationshipGraph from '$lib/components/RelationshipGraph.svelte';
	import TabBar from '$lib/components/ui/TabBar.svelte';
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
	import EditableField from '$lib/components/ui/EditableField.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
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
	let debouncedSearch = $state('');
	let searchDebounceTimer: ReturnType<typeof setTimeout>;
	let libraryTypeFilter = $state('');
	let selectedCard = $state<StoryCardDetail | null>(null);
	let loadingCard = $state(false);
	let libraryTab = $state<'detail' | 'gaps'>('detail');
	let libraryDetailsOpen = $state(false);
	let auditResult = $state<AuditResponse | null>(null);
	let auditing = $state(false);

	// ── State tool ──
	let stateSnapshot = $state<StateSnapshot | null>(null);
	let showAllEvents = $state(false);

	// ── Trust editing ──
	let trustEditRow = $state<string | null>(null); // "charA|charB" key
	let trustChangeVal = $state(0);
	let trustReason = $state('');
	let trustDirection = $state('neutral');
	let trustSaving = $state(false);
	let showTrustConfirm = $state(false);
	let pendingTrustSubmit = $state<(() => void) | null>(null);

	async function submitTrustChange(charA: string, charB: string) {
		if (!trustReason.trim() || trustChangeVal === 0) return;
		trustSaving = true;
		try {
			await adjustTrust(charA, charB, {
				trust_change: trustChangeVal,
				reason: trustReason,
				direction: trustDirection,
			});
			addToast(`Trust adjusted: ${charA} → ${charB} by ${trustChangeVal > 0 ? '+' : ''}${trustChangeVal}`, 'success');
			trustEditRow = null;
			trustChangeVal = 0;
			trustReason = '';
			trustDirection = 'neutral';
			// Refresh state
			stateSnapshot = await getFullState();
		} catch (e: any) {
			addToast(e.message ?? 'Failed to adjust trust', 'error');
		} finally {
			trustSaving = false;
		}
	}

	function handleTrustSubmit(charA: string, charB: string) {
		if (Math.abs(trustChangeVal) > 5) {
			pendingTrustSubmit = () => submitTrustChange(charA, charB);
			showTrustConfirm = true;
		} else {
			submitTrustChange(charA, charB);
		}
	}

	async function handleSceneFieldSave(field: string, newValue: string) {
		await updateScene({ [field]: newValue });
		if (stateSnapshot) {
			stateSnapshot = { ...stateSnapshot, scene: { ...stateSnapshot.scene, [field]: newValue } };
		}
	}

	async function handleCharFieldSave(name: string, field: string, newValue: string) {
		await updateCharacter(name, { [field]: newValue });
		if (stateSnapshot) {
			const chars = { ...stateSnapshot.characters };
			if (chars[name]) {
				chars[name] = { ...chars[name], [field]: newValue };
			}
			stateSnapshot = { ...stateSnapshot, characters: chars };
		}
	}

	async function removeCondition(name: string, condition: string) {
		const char = stateSnapshot?.characters[name];
		if (!char) return;
		const newConditions = char.conditions.filter(c => c !== condition);
		await updateCharacter(name, { conditions: newConditions });
		if (stateSnapshot) {
			const chars = { ...stateSnapshot.characters };
			chars[name] = { ...chars[name], conditions: newConditions };
			stateSnapshot = { ...stateSnapshot, characters: chars };
		}
	}

	let addConditionName = $state('');
	let addConditionValue = $state('');

	async function addCondition(name: string) {
		if (!addConditionValue.trim()) return;
		const char = stateSnapshot?.characters[name];
		if (!char) return;
		const newConditions = [...char.conditions, addConditionValue.trim()];
		await updateCharacter(name, { conditions: newConditions });
		if (stateSnapshot) {
			const chars = { ...stateSnapshot.characters };
			chars[name] = { ...chars[name], conditions: newConditions };
			stateSnapshot = { ...stateSnapshot, characters: chars };
		}
		addConditionValue = '';
		addConditionName = '';
	}

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

	// ── NPC Relationship Graph ──
	let graphTab = $state<'connections' | 'relationships'>('connections');
	let relGraphData = $state<RelationshipGraphResponse | null>(null);
	let relGraphLoading = $state(false);
	let relGraphSelectedNode = $state<RelGraphNode | null>(null);

	async function loadRelGraph() {
		if (relGraphData) return;
		relGraphLoading = true;
		try {
			relGraphData = await getRelationshipGraph();
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load relationship graph', 'error');
		} finally {
			relGraphLoading = false;
		}
	}

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

	// Debounce search input to avoid filtering/sorting on every keystroke
	$effect(() => {
		const val = librarySearch;
		clearTimeout(searchDebounceTimer);
		searchDebounceTimer = setTimeout(() => { debouncedSearch = val; }, 200);
		return () => clearTimeout(searchDebounceTimer);
	});

	let filteredCards = $derived(
		cards
			.filter(c => {
				if (libraryTypeFilter && c.card_type !== libraryTypeFilter) return false;
				if (debouncedSearch.trim()) {
					const q = debouncedSearch.toLowerCase();
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
				<div class="bg-surface border border-border-custom rounded-lg flex flex-col" style="max-height: calc(100vh - 180px)">
					<div class="flex items-center gap-2 px-4 py-2.5 border-b border-border-custom shrink-0">
						<BackButton label="Back to library" onclick={() => (selectedCard = null)} />
					</div>

					<!-- Fixed header + collapsible details -->
					<div class="px-4 pt-4 shrink-0">
						<!-- Header -->
						<div class="flex items-center gap-2 mb-3">
							<Badge color={cardTypeColors(selectedCard.card_type).text} bg={cardTypeColors(selectedCard.card_type).bg} dot={cardTypeColors(selectedCard.card_type).hex}>{selectedCard.card_type.replaceAll('_', ' ')}</Badge>
							<h3 class="text-base font-semibold text-text font-serif">{selectedCard.name}</h3>
							{#if selectedCard.importance}
								{@const imp = importanceColors(selectedCard.importance)}
								<Badge color={imp.text} bg={imp.bg}>{selectedCard.importance}</Badge>
							{/if}
						</div>

						<!-- Collapsible frontmatter details -->
						{#if Object.keys(selectedCard.frontmatter).length > 0}
							<button
								class="flex items-center gap-1.5 mb-3 text-xs text-text-dim hover:text-text transition-colors cursor-pointer bg-transparent border-none p-0"
								onclick={() => (libraryDetailsOpen = !libraryDetailsOpen)}
							>
								<span class="text-[10px] transition-transform inline-block" style="transform: rotate({libraryDetailsOpen ? '90deg' : '0deg'})">&#9654;</span>
								<SectionLabel>Details</SectionLabel>
							</button>
							{#if libraryDetailsOpen}
								<div class="mb-3 pl-4 py-2 border-l-2 border-border-custom/60 grid grid-cols-2 gap-x-4 gap-y-1">
									{#each Object.entries(selectedCard.frontmatter) as [key, val]}
										<div class="flex gap-2 text-xs py-0.5">
											<span class="text-text-dim shrink-0">{key}</span>
											<span class="text-text break-all">{typeof val === 'object' ? JSON.stringify(val) : String(val)}</span>
										</div>
									{/each}
								</div>
							{/if}
						{/if}
					</div>

					<!-- Scrollable body + connections -->
					<div class="flex-1 overflow-y-auto px-4 pb-4 min-h-0">
						<!-- Body content (frontmatter stripped) -->
						{#if selectedCard.body}
							<p class="text-[13px] text-text-dim leading-relaxed whitespace-pre-wrap mb-4">{selectedCard.body}</p>
						{/if}

						<!-- Connections -->
						{#if selectedCard.connections.length > 0}
							<div class="mt-3">
								<div class="mb-2"><SectionLabel>Connections ({selectedCard.connections.length})</SectionLabel></div>
								<div class="flex flex-wrap gap-1.5">
									{#each selectedCard.connections as conn}
										<EntityChip label={conn.connection_type} name={conn.to_entity} variant="subtle" onclick={() => selectCardByName(conn.to_entity)} />
									{/each}
								</div>
							</div>
						{:else}
							<p class="text-xs text-warning mt-3">No connections (orphan card)</p>
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
							{#each [['location', 'Location', stateSnapshot.scene.location], ['time_of_day', 'Time of Day', stateSnapshot.scene.time_of_day], ['mood', 'Mood', stateSnapshot.scene.mood], ['in_story_timestamp', 'Timestamp', stateSnapshot.scene.in_story_timestamp]] as [field, label, val]}
								<div class="flex items-start gap-2 text-xs">
									<span class="text-text-dim shrink-0 w-24">{label}</span>
									<div class="flex-1">
										<EditableField
											value={val ?? ''}
											placeholder="Not set"
											onSave={(v) => handleSceneFieldSave(field as string, v)}
										/>
									</div>
								</div>
							{/each}
						</div>
					</CardSection>

					<!-- Characters card -->
					<CardSection title="Characters" compact>
						<div class="px-4 py-3 flex flex-col gap-3">
							{#each [...playerChars, ...npcChars] as entry}
								{@const name = entry[0]}
								{@const char = entry[1]}
								<div class="text-[13px]">
									<span class="font-medium text-text">{name}</span>
									{#if char.is_player_character}
										<Badge color="var(--color-accent)" bg="var(--color-accent-soft)">PC</Badge>
									{/if}

									<div class="mt-1 space-y-0.5">
										<div class="flex items-start gap-2 text-xs">
											<span class="text-text-dim shrink-0 w-20">Emotion</span>
											<div class="flex-1">
												<EditableField
													value={char.emotional_state ?? ''}
													placeholder="Not set"
													onSave={(v) => handleCharFieldSave(name, 'emotional_state', v)}
												/>
											</div>
										</div>
										<div class="flex items-start gap-2 text-xs">
											<span class="text-text-dim shrink-0 w-20">Location</span>
											<div class="flex-1">
												<EditableField
													value={char.location ?? ''}
													placeholder="Not set"
													onSave={(v) => handleCharFieldSave(name, 'location', v)}
												/>
											</div>
										</div>
									</div>

									<!-- Conditions (chip-style with remove + add) -->
									<div class="flex items-center gap-1 mt-1 flex-wrap">
										{#each char.conditions as cond}
											<span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-surface2 rounded text-[10px] text-text-dim">
												{cond}
												<button
													class="text-text-dim/60 hover:text-error transition-colors ml-0.5"
													onclick={() => removeCondition(name, cond)}
													title="Remove condition"
												>&times;</button>
											</span>
										{/each}
										{#if addConditionName === name}
											<input
												type="text"
												bind:value={addConditionValue}
												placeholder="New condition"
												onkeydown={(e) => { if (e.key === 'Enter') addCondition(name); if (e.key === 'Escape') addConditionName = ''; }}
												class="px-1.5 py-0.5 rounded border border-border-custom bg-bg-subtle text-[10px] text-text w-24
													focus:outline-none focus:ring-1 focus:ring-accent"
											/>
										{:else}
											<button
												class="text-[10px] text-accent hover:text-accent-hover transition-colors"
												onclick={() => { addConditionName = name; addConditionValue = ''; }}
											>+ add</button>
										{/if}
									</div>
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
										<th class="pb-1 pr-3">Stage</th>
										<th class="pb-1"></th>
									</tr>
								</thead>
								<tbody>
									{#each stateSnapshot.relationships as rel}
										{@const rowKey = `${rel.character_a}|${rel.character_b}`}
										<tr class="border-b border-border-custom/30">
											<td class="py-1 pr-3 text-text">{rel.character_a}</td>
											<td class="py-1 pr-3 text-text">{rel.character_b}</td>
											<td class="py-1 pr-3 font-mono {rel.live_trust_score > 0 ? 'text-success' : rel.live_trust_score < 0 ? 'text-error' : 'text-text-dim'}">
												{rel.live_trust_score > 0 ? '+' : ''}{rel.live_trust_score}
											</td>
											<td class="py-1 pr-3">
												<span class="px-1 py-0.5 rounded text-[10px]" style="{trustStageColor(rel.trust_stage)}">{rel.trust_stage}</span>
											</td>
											<td class="py-1">
												<button
													class="text-[10px] text-accent hover:text-accent-hover transition-colors"
													onclick={() => { trustEditRow = trustEditRow === rowKey ? null : rowKey; trustChangeVal = 0; trustReason = ''; trustDirection = 'neutral'; }}
												>{trustEditRow === rowKey ? 'Cancel' : 'Adjust'}</button>
											</td>
										</tr>
										{#if trustEditRow === rowKey}
											<tr>
												<td colspan="5" class="pb-2 pt-1">
													<div class="flex items-end gap-2 bg-surface2/40 rounded-lg p-2">
														<div>
															<label for="trust-change" class="text-[10px] text-text-dim block mb-0.5">Change</label>
															<input id="trust-change" type="number" bind:value={trustChangeVal}
																class="w-16 px-1.5 py-1 rounded border border-border-custom bg-bg-subtle text-xs text-text
																	focus:outline-none focus:ring-1 focus:ring-accent" />
														</div>
														<div class="flex-1">
															<label for="trust-reason" class="text-[10px] text-text-dim block mb-0.5">Reason</label>
															<input id="trust-reason" type="text" bind:value={trustReason} placeholder="Why?"
																class="w-full px-1.5 py-1 rounded border border-border-custom bg-bg-subtle text-xs text-text
																	focus:outline-none focus:ring-1 focus:ring-accent" />
														</div>
														<div>
															<label for="trust-direction" class="text-[10px] text-text-dim block mb-0.5">Direction</label>
															<select id="trust-direction" bind:value={trustDirection}
																class="px-1.5 py-1 rounded border border-border-custom bg-bg-subtle text-xs text-text
																	focus:outline-none focus:ring-1 focus:ring-accent">
																<option value="neutral">neutral</option>
																<option value="a_to_b">A → B</option>
																<option value="b_to_a">B → A</option>
															</select>
														</div>
														<button
															class="px-2.5 py-1 text-[11px] rounded bg-accent text-text-on-accent hover:bg-accent-hover transition-colors
																disabled:opacity-50"
															disabled={trustSaving || !trustReason.trim() || trustChangeVal === 0}
															onclick={() => handleTrustSubmit(rel.character_a, rel.character_b)}
														>{trustSaving ? '...' : 'Apply'}</button>
													</div>
												</td>
											</tr>
										{/if}
									{/each}
								</tbody>
							</table>
						</div>
					</CardSection>
					</div>
				{/if}
			{/if}

			<!-- Trust confirm dialog -->
			<ConfirmDialog
				bind:open={showTrustConfirm}
				title="Large Trust Change"
				message="You're applying a trust change greater than ±5. This is a significant shift. Are you sure?"
				confirmLabel="Apply Change"
				variant="danger"
				onConfirm={() => { if (pendingTrustSubmit) pendingTrustSubmit(); pendingTrustSubmit = null; }}
				onCancel={() => { pendingTrustSubmit = null; }}
			/>

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

				<!-- Tab bar -->
				<div class="px-3 pt-2 border-b border-border-custom bg-surface z-20 relative">
					<TabBar
						items={[{id: 'connections', label: 'Card Connections'}, {id: 'relationships', label: 'NPC Relationships'}]}
						bind:active={graphTab}
						onselect={(id) => { if (id === 'relationships') loadRelGraph(); }}
					/>
				</div>

				<!-- Graph canvas (full area) -->
				<div class="flex-1 min-h-0">
					{#if graphTab === 'connections'}
						{#if !graphFilteredData}
							<div class="flex items-center justify-center h-full text-xs text-text-dim">Loading graph data...</div>
						{:else}
							<ForceGraph data={graphFilteredData} filter={graphFilter} onNodeClick={handleGraphNodeClick} />
						{/if}
					{:else}
						{#if relGraphLoading}
							<div class="flex items-center justify-center h-full text-xs text-text-dim">Loading relationship graph...</div>
						{:else if relGraphData}
							<RelationshipGraph data={relGraphData} onNodeClick={(n) => { relGraphSelectedNode = n; }} />
						{:else}
							<div class="flex items-center justify-center h-full text-xs text-text-dim">No relationship data available.</div>
						{/if}
					{/if}
				</div>

				<!-- Floating filter panel (top-right, connections tab only) -->
				{#if graphTab === 'connections'}
				<div class="absolute top-14 right-3 z-10">
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

				<!-- Floating card preview (top-left, on node click — connections tab only) -->
				{#if graphSelectedNode}
					<div class="absolute top-14 left-3 z-10 bg-surface/95 backdrop-blur-sm border border-border-custom rounded-[10px] shadow-lg w-72 max-h-[60%] overflow-y-auto">
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
				{/if}

				<!-- NPC relationship node detail (relationships tab) -->
				{#if graphTab === 'relationships' && relGraphSelectedNode}
					<div class="absolute top-14 left-3 z-10 bg-surface/95 backdrop-blur-sm border border-border-custom rounded-[10px] shadow-lg w-64">
						<div class="flex items-center justify-between px-3 py-2 border-b border-border-custom">
							<span class="text-xs font-medium text-text">{relGraphSelectedNode.name}</span>
							<button
								class="text-xs text-text-dim hover:text-text transition-colors"
								onclick={() => (relGraphSelectedNode = null)}
							>Close</button>
						</div>
						<div class="p-3 space-y-1.5 text-xs">
							{#if relGraphSelectedNode.is_player_character}
								<Badge color="var(--color-accent)" bg="var(--color-accent-soft)">Player Character</Badge>
							{/if}
							{#if relGraphSelectedNode.importance}
								<div class="flex gap-2"><span class="text-text-dim w-20">Importance</span><span class="text-text">{relGraphSelectedNode.importance}</span></div>
							{/if}
							{#if relGraphSelectedNode.primary_archetype}
								<div class="flex gap-2"><span class="text-text-dim w-20">Archetype</span><span class="text-text">{relGraphSelectedNode.primary_archetype}</span></div>
							{/if}
							{#if relGraphSelectedNode.emotional_state}
								<div class="flex gap-2"><span class="text-text-dim w-20">Emotion</span><span class="text-text italic font-serif">{relGraphSelectedNode.emotional_state}</span></div>
							{/if}
							{#if relGraphSelectedNode.location}
								<div class="flex gap-2"><span class="text-text-dim w-20">Location</span><span class="text-text">{relGraphSelectedNode.location}</span></div>
							{/if}
							<div class="flex gap-2">
								<span class="text-text-dim w-20">Trust</span>
								<span class="font-mono {relGraphSelectedNode.trust_score > 0 ? 'text-success' : relGraphSelectedNode.trust_score < 0 ? 'text-error' : 'text-text-dim'}">
									{relGraphSelectedNode.trust_score > 0 ? '+' : ''}{relGraphSelectedNode.trust_score}
								</span>
								<span class="px-1 py-0.5 rounded text-[10px]" style="{trustStageColor(relGraphSelectedNode.trust_stage)}">{relGraphSelectedNode.trust_stage}</span>
							</div>
						</div>
					</div>
				{/if}

				<!-- NPC relationship metadata (relationships tab, top-right) -->
				{#if graphTab === 'relationships' && relGraphData}
					<div class="absolute top-14 right-3 z-10 bg-surface/95 backdrop-blur-sm border border-border-custom rounded-lg shadow-lg px-3 py-2">
						<p class="text-[10px] text-text-dim">{relGraphData.metadata.total_npcs} NPCs · {relGraphData.metadata.total_edges} edges</p>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
