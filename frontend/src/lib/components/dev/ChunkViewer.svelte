<script lang="ts">
	import { onMount } from 'svelte';
	import { listCards } from '$lib/api/cards';
	import {
		getVectorStats, listChunks, getChunksForFile, searchDebug,
		reindexExchanges, listExchangeChunks,
		type ExchangeChunk,
	} from '$lib/api/vectors';
	import { activeRP } from '$lib/stores/rp';
	import type { StoryCardSummary, ChunkRow, VectorStats, DebugSearchResult } from '$lib/types';

	const tabs = [
		{ id: 'inspect', label: 'Chunk Inspector' },
		{ id: 'browse',  label: 'Chunk Browser'   },
		{ id: 'query',   label: 'Query Tester'    },
	];

	let activeTab = $state('inspect');

	// Stats
	let stats = $state<VectorStats | null>(null);
	let statsError = $state('');

	// Chunk Inspector tab — unified card + exchange list
	let cards = $state<StoryCardSummary[]>([]);
	let exchangeChunks = $state<ExchangeChunk[]>([]);
	let inspectTypeFilter = $state('');
	let inspectLoading = $state(true);
	let inspectError = $state('');

	// Selected item detail
	let selectedItem = $state<{ kind: 'card'; card: StoryCardSummary } | { kind: 'exchange'; exNum: number } | null>(null);
	let selectedChunks = $state<ChunkRow[]>([]);
	let selectedExchangeChunks = $state<ExchangeChunk[]>([]);
	let detailLoading = $state(false);
	let detailError = $state('');

	// Chunk Browser tab
	let browseAllChunks = $state<ChunkRow[]>([]);
	let browseExchangeChunks = $state<ExchangeChunk[]>([]);
	let browseLoading = $state(false);
	let browseError = $state('');
	let browseSearch = $state('');
	let browseSourceFilter = $state('');
	let browseTypeFilter = $state('');
	let browseLoaded = $state(false);

	// Reindex
	let reindexing = $state(false);
	let reindexResult = $state<{ total_exchanges: number; embedded: number; failed: number } | null>(null);

	// Query Tester tab
	let queryText = $state('');
	let queryResults = $state<DebugSearchResult[]>([]);
	let queryLoading = $state(false);
	let queryError = $state('');
	let queryRan = $state(false);

	onMount(async () => {
		try {
			const [statsRes, cardsRes, exchRes] = await Promise.all([
				getVectorStats(),
				listCards(),
				listExchangeChunks({}),
			]);
			stats = statsRes;
			cards = cardsRes.cards;
			exchangeChunks = exchRes;
		} catch (e: any) {
			inspectError = e.message;
		} finally {
			inspectLoading = false;
		}
	});

	// Grouped exchange numbers for the list
	let exchangeNumbers = $derived([...new Set(exchangeChunks.map(c => c.exchange_number))].sort((a, b) => a - b));

	// Build unified list items
	interface ListItem {
		kind: 'card' | 'exchange';
		type: string;
		label: string;
		sublabel: string;
		key: string;
	}

	let cardItems = $derived(cards.map(c => ({
		kind: 'card' as const,
		type: c.card_type ?? 'unknown',
		label: c.name,
		sublabel: c.card_type ?? '',
		key: `card:${c.file_path}`,
		card: c,
	})));

	let exchangeItems = $derived(exchangeNumbers.map(n => ({
		kind: 'exchange' as const,
		type: 'exchange',
		label: `Exchange #${n}`,
		sublabel: `${exchangeChunks.filter(c => c.exchange_number === n).length} chunks`,
		key: `ex:${n}`,
		exNum: n,
	})));

	let allListItems = $derived([...cardItems, ...exchangeItems]);
	let inspectTypes = $derived([...new Set(allListItems.map(i => i.type).filter(Boolean))].sort());
	let filteredListItems = $derived(
		inspectTypeFilter
			? allListItems.filter(i => i.type === inspectTypeFilter)
			: allListItems
	);

	let selectedKey = $derived(
		selectedItem
			? (selectedItem.kind === 'card' ? `card:${selectedItem.card.file_path}` : `ex:${selectedItem.exNum}`)
			: ''
	);

	async function selectCardItem(card: StoryCardSummary) {
		if (selectedItem?.kind === 'card' && selectedItem.card.file_path === card.file_path) return;
		selectedItem = { kind: 'card', card };
		selectedChunks = [];
		selectedExchangeChunks = [];
		detailError = '';
		detailLoading = true;
		try {
			selectedChunks = await getChunksForFile(card.file_path);
		} catch (e: any) {
			detailError = e.message;
		} finally {
			detailLoading = false;
		}
	}

	function selectExchangeItem(exNum: number) {
		if (selectedItem?.kind === 'exchange' && selectedItem.exNum === exNum) return;
		selectedItem = { kind: 'exchange', exNum };
		selectedChunks = [];
		selectedExchangeChunks = exchangeChunks.filter(c => c.exchange_number === exNum);
		detailError = '';
		detailLoading = false;
	}

	// Chunk Browser
	async function loadBrowse() {
		if (browseLoaded) return;
		browseLoading = true;
		browseError = '';
		try {
			const [cardChunks, exchChunks] = await Promise.all([
				listChunks({ limit: 500 }),
				listExchangeChunks({}),
			]);
			browseAllChunks = cardChunks;
			browseExchangeChunks = exchChunks;
			browseLoaded = true;
		} catch (e: any) {
			browseError = e.message;
		} finally {
			browseLoading = false;
		}
	}

	// Browse items normalization
	let cardBrowseItems = $derived(browseAllChunks.map(c => ({
		source: 'card' as const,
		content: c.content,
		type: c.card_type ?? 'unknown',
		label: shortPath(c.file_path),
		sublabel: `chunk ${c.chunk_index}/${c.total_chunks}`,
		hasEmbedding: c.has_embedding,
	})));

	let exchangeBrowseItems = $derived(browseExchangeChunks.map(c => ({
		source: 'exchange' as const,
		content: c.text,
		type: 'exchange',
		label: `Exchange #${c.exchange_number}`,
		sublabel: c.speaker,
		hasEmbedding: true,
	})));

	let allBrowseItems = $derived([...cardBrowseItems, ...exchangeBrowseItems]);

	let filteredBrowseItems = $derived(allBrowseItems.filter(item => {
		if (browseSearch && !item.content.toLowerCase().includes(browseSearch.toLowerCase())) return false;
		if (browseSourceFilter === 'cards' && item.source !== 'card') return false;
		if (browseSourceFilter === 'exchanges' && item.source !== 'exchange') return false;
		if (browseTypeFilter && item.type !== browseTypeFilter) return false;
		return true;
	}));

	let browseTypes = $derived([...new Set(allBrowseItems.map(i => i.type).filter(Boolean))].sort());

	// Query
	async function runQuery() {
		if (!queryText.trim()) return;
		queryLoading = true;
		queryError = '';
		queryResults = [];
		queryRan = false;
		try {
			queryResults = await searchDebug(queryText.trim(), 20);
			queryRan = true;
		} catch (e: any) {
			queryError = e.message;
		} finally {
			queryLoading = false;
		}
	}

	// Reindex
	async function handleReindex() {
		reindexing = true;
		reindexResult = null;
		try {
			const params: Record<string, string> = {};
			if ($activeRP) params.rp_folder = $activeRP.rp_folder;
			const result = await reindexExchanges(params);
			reindexResult = result;
			stats = await getVectorStats();
			// Refresh exchange data
			exchangeChunks = await listExchangeChunks({});
			browseLoaded = false;
			if (activeTab === 'browse') loadBrowse();
		} catch (e: any) {
			statsError = e.message ?? 'Reindex failed';
		} finally {
			reindexing = false;
		}
	}

	function handleTabClick(id: string) {
		activeTab = id;
		if (id === 'browse') loadBrowse();
	}

	function embadgeColor(result: DebugSearchResult) {
		if (result.found_by === 'both')   return 'bg-success/20 text-success';
		if (result.found_by === 'vector') return 'bg-accent/20 text-accent';
		return 'bg-warning/20 text-warning';
	}

	function shortPath(fp: string | null): string {
		if (!fp) return '\u2014';
		const parts = fp.replace(/\\/g, '/').split('/');
		return parts[parts.length - 1].replace('.md', '');
	}

	function sourceColor(source: string) {
		return source === 'exchange' ? 'bg-accent/15 text-accent' : 'bg-bg-subtle text-text-dim';
	}

	function typeColor(type: string) {
		switch (type) {
			case 'exchange':        return 'text-accent';
			case 'character':       return 'text-success';
			case 'npc':             return 'text-success/70';
			case 'location':        return 'text-warning';
			case 'secret':          return 'text-error';
			case 'memory':          return 'text-purple-400';
			case 'plot_thread':     return 'text-blue-400';
			default:                return 'text-text-dim';
		}
	}
</script>

<div class="space-y-3">
	<!-- Stats bar -->
	{#if stats}
		<div class="flex items-center gap-4 text-xs text-text-dim bg-surface border border-border-custom rounded-lg px-4 py-2">
			<span><span class="text-text font-medium">{stats.total_chunks}</span> card chunks</span>
			<span>·</span>
			<span><span class="text-text font-medium">{stats.total_files}</span> files</span>
			<span>·</span>
			<span>
				<span class="text-text font-medium">{stats.chunks_with_embeddings}</span>
				/ {stats.total_chunks} embedded
			</span>
			<span>·</span>
			<span><span class="text-text font-medium">{exchangeChunks.length}</span> exchange chunks</span>
			{#if stats.cards_without_vectors.length}
				<span>·</span>
				<span class="text-warning">{stats.cards_without_vectors.length} cards missing vectors</span>
			{/if}
			<span class="ml-auto flex items-center gap-2">
				{#if reindexResult}
					<span class="text-success">
						{reindexResult.embedded}/{reindexResult.total_exchanges} embedded
						{#if reindexResult.failed > 0}
							<span class="text-warning">({reindexResult.failed} failed)</span>
						{/if}
					</span>
				{/if}
				<button
					onclick={handleReindex}
					disabled={reindexing}
					class="px-2.5 py-1 bg-bg-subtle border border-border-custom rounded text-xs text-text-dim
						hover:text-text hover:bg-bg-subtle transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{reindexing ? 'Reindexing...' : 'Reindex Exchanges'}
				</button>
			</span>
		</div>
	{:else if statsError}
		<div class="text-xs text-error px-1">{statsError}</div>
	{/if}

	<!-- Tab bar + content -->
	<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
		<div class="flex border-b border-border-custom">
			{#each tabs as tab}
				<button
					class="px-4 py-2.5 text-sm transition-colors border-r border-border-custom last:border-r-0
						{activeTab === tab.id
							? 'bg-accent/10 text-accent font-medium'
							: 'text-text-dim hover:text-text hover:bg-bg-subtle'}"
					onclick={() => handleTabClick(tab.id)}
				>
					{tab.label}
				</button>
			{/each}
		</div>

		<!-- Chunk Inspector -->
		{#if activeTab === 'inspect'}
			<div class="flex" style="min-height: 400px;">
				<!-- Item list -->
				<div class="w-64 border-r border-border-custom flex flex-col">
					<div class="px-3 py-2 text-xs text-text-dim border-b border-border-custom flex items-center gap-2">
						<span class="shrink-0">{filteredListItems.length} items</span>
						<select
							bind:value={inspectTypeFilter}
							class="ml-auto bg-bg-subtle border border-border-custom rounded px-1.5 py-0.5 text-xs text-text-dim"
						>
							<option value="">All types</option>
							{#each inspectTypes as t}
								<option value={t}>{t}</option>
							{/each}
						</select>
					</div>
					<div class="overflow-y-auto flex-1">
						{#if inspectLoading}
							<div class="p-3 space-y-1.5">
								{#each [1,2,3,4,5] as _}
									<div class="h-7 bg-bg-subtle rounded animate-pulse"></div>
								{/each}
							</div>
						{:else if inspectError && allListItems.length === 0}
							<div class="p-3 text-xs text-error">{inspectError}</div>
						{:else if filteredListItems.length === 0}
							<div class="p-3 text-xs text-text-dim">No items match filter.</div>
						{:else}
							{#each filteredListItems as item}
								<button
									class="w-full text-left px-3 py-2 text-sm border-b border-border-custom/50
										hover:bg-bg-subtle transition-colors flex items-center justify-between gap-2
										{selectedKey === item.key ? 'bg-accent/10 text-accent' : 'text-text-dim'}"
									onclick={() => item.kind === 'card' ? selectCardItem(item.card) : selectExchangeItem(item.exNum)}
								>
									<span class="truncate">{item.label}</span>
									<span class="text-xs opacity-50 shrink-0 {typeColor(item.type)}">{item.type}</span>
								</button>
							{/each}
						{/if}
					</div>
				</div>

				<!-- Detail panel -->
				<div class="flex-1 overflow-y-auto p-4">
					{#if !selectedItem}
						<div class="h-full flex items-center justify-center text-sm text-text-dim">
							Select an item to see its chunks
						</div>
					{:else if detailLoading}
						<div class="space-y-2">
							{#each [1,2,3] as _}
								<div class="h-24 bg-bg-subtle rounded-md animate-pulse"></div>
							{/each}
						</div>
					{:else if detailError}
						<div class="text-sm text-error">{detailError}</div>

					<!-- Card chunks -->
					{:else if selectedItem.kind === 'card'}
						{#if selectedChunks.length === 0}
							<div class="text-sm text-text-dim text-center py-8">No chunks found for this card.</div>
						{:else}
							<div class="space-y-3">
								<div class="text-xs text-text-dim flex items-center gap-3">
									<span class="font-medium text-text">{selectedItem.card.name}</span>
									<span>·</span>
									<span>{selectedChunks.length} chunk{selectedChunks.length !== 1 ? 's' : ''}</span>
									<span>·</span>
									<span>{selectedChunks.filter(c => c.has_embedding).length} embedded</span>
								</div>
								{#each selectedChunks as chunk}
									<div class="border border-border-custom rounded-md overflow-hidden text-xs">
										<div class="flex items-center gap-3 px-3 py-1.5 bg-bg-subtle border-b border-border-custom text-text-dim">
											<span class="font-mono">chunk {chunk.chunk_index + 1} / {chunk.total_chunks}</span>
											<span>·</span>
											<span>{chunk.content.length} chars</span>
											<span>·</span>
											<span class="{chunk.has_embedding ? 'text-success' : 'text-warning'}">
												{chunk.has_embedding ? 'embedded' : 'no embedding'}
											</span>
										</div>
										<pre class="p-3 whitespace-pre-wrap font-mono leading-relaxed text-text-dim overflow-x-auto">{chunk.content}</pre>
									</div>
								{/each}
							</div>
						{/if}

					<!-- Exchange chunks -->
					{:else if selectedItem.kind === 'exchange'}
						{#if selectedExchangeChunks.length === 0}
							<div class="text-sm text-text-dim text-center py-8">No chunks for this exchange.</div>
						{:else}
							<div class="space-y-3">
								<div class="text-xs text-text-dim flex items-center gap-3">
									<span class="font-medium text-accent">Exchange #{selectedItem.exNum}</span>
									<span>·</span>
									<span>{selectedExchangeChunks.length} chunk{selectedExchangeChunks.length !== 1 ? 's' : ''}</span>
								</div>
								{#each selectedExchangeChunks as chunk}
									<div class="border border-border-custom rounded-md overflow-hidden text-xs">
										<div class="flex items-center gap-3 px-3 py-1.5 bg-bg-subtle border-b border-border-custom text-text-dim">
											<span class="px-1.5 py-0.5 rounded text-[10px] {chunk.speaker === 'user' ? 'bg-accent/15 text-accent' : 'bg-success/15 text-success'}">
												{chunk.speaker}
											</span>
											<span>{chunk.text.length} chars</span>
											{#if chunk.session_id}
												<span>·</span>
												<span class="font-mono truncate max-w-[120px]">{chunk.session_id}</span>
											{/if}
											{#if chunk.in_story_timestamp}
												<span>·</span>
												<span>{chunk.in_story_timestamp}</span>
											{/if}
										</div>
										<pre class="p-3 whitespace-pre-wrap font-mono leading-relaxed text-text-dim overflow-x-auto">{chunk.text}</pre>
									</div>
								{/each}
							</div>
						{/if}
					{/if}
				</div>
			</div>

		<!-- Chunk Browser -->
		{:else if activeTab === 'browse'}
			<div class="p-3 space-y-3">
				<div class="flex gap-2">
					<input
						type="text"
						placeholder="Search chunk content..."
						bind:value={browseSearch}
						class="flex-1 bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm
							text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
					/>
					<select
						bind:value={browseSourceFilter}
						class="bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text-dim"
					>
						<option value="">All sources</option>
						<option value="cards">Cards only</option>
						<option value="exchanges">Exchanges only</option>
					</select>
					<select
						bind:value={browseTypeFilter}
						class="bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text-dim"
					>
						<option value="">All types</option>
						{#each browseTypes as t}
							<option value={t}>{t}</option>
						{/each}
					</select>
				</div>

				{#if browseLoading}
					<div class="space-y-1.5">
						{#each [1,2,3,4,5] as _}
							<div class="h-14 bg-bg-subtle rounded animate-pulse"></div>
						{/each}
					</div>
				{:else if browseError}
					<div class="text-sm text-error">{browseError}</div>
				{:else if filteredBrowseItems.length === 0}
					<div class="text-sm text-text-dim text-center py-8">
						{browseLoaded ? 'No chunks match filters.' : 'Loading...'}
					</div>
				{:else}
					<div class="text-xs text-text-dim mb-1">{filteredBrowseItems.length} chunks</div>
					<div class="space-y-1.5 max-h-[480px] overflow-y-auto">
						{#each filteredBrowseItems as item}
							<div class="border border-border-custom rounded-md text-xs overflow-hidden">
								<div class="flex items-center gap-2 px-3 py-1.5 bg-bg-subtle text-text-dim">
									<span class="px-1.5 py-0.5 rounded text-[10px] {sourceColor(item.source)}">{item.source}</span>
									<span class="font-medium text-text truncate">{item.label}</span>
									<span class="text-text-dim/50">·</span>
									<span>{item.type}</span>
									<span class="text-text-dim/50">·</span>
									<span>{item.sublabel}</span>
									<span class="ml-auto {item.hasEmbedding ? 'text-success' : 'text-warning'}">
										{item.hasEmbedding ? '✓' : '⚠'}
									</span>
								</div>
								<p class="px-3 py-2 text-text-dim line-clamp-2 font-mono leading-relaxed">{item.content}</p>
							</div>
						{/each}
					</div>
				{/if}
			</div>

		<!-- Query Tester -->
		{:else if activeTab === 'query'}
			<div class="p-3 space-y-3">
				<div class="flex gap-2">
					<input
						type="text"
						placeholder="Enter a search query..."
						bind:value={queryText}
						onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && runQuery()}
						class="flex-1 bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm
							text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
					/>
					<button
						onclick={runQuery}
						disabled={queryLoading || !queryText.trim()}
						class="bg-accent text-white text-sm font-medium py-2 px-4 rounded-md
							hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
					>
						{queryLoading ? '...' : 'Search'}
					</button>
				</div>

				<div class="text-xs text-text-dim bg-bg-subtle rounded-md px-3 py-2">
					chunk_size=1000 · overlap=200 · cosine×0.7 + BM25×0.3 → RRF(k=60) · threshold=0.7
				</div>

				{#if queryError}
					<div class="text-sm text-error">{queryError}</div>
				{:else if queryLoading}
					<div class="space-y-2">
						{#each [1,2,3] as _}
							<div class="h-20 bg-bg-subtle rounded animate-pulse"></div>
						{/each}
					</div>
				{:else if queryRan && queryResults.length === 0}
					<div class="text-sm text-text-dim text-center py-8">No results above threshold.</div>
				{:else if queryResults.length > 0}
					<div class="space-y-2 max-h-[480px] overflow-y-auto">
						{#each queryResults as r, i}
							<div class="border border-border-custom rounded-md text-xs overflow-hidden">
								<div class="flex items-center gap-2 px-3 py-1.5 bg-bg-subtle text-text-dim flex-wrap">
									<span class="text-text font-medium">#{i + 1}</span>
									<span class="truncate max-w-[160px]">{shortPath(r.file_path)}</span>
									<span class="text-text-dim/50">·</span>
									<span>{r.card_type ?? '\u2014'}</span>
									<span class="text-text-dim/50">·</span>
									<span>chunk {r.chunk_index}</span>
									<span class="ml-auto flex items-center gap-1.5">
										<span class="px-1.5 py-0.5 rounded text-[10px] font-mono {embadgeColor(r)}">
											{r.found_by}
										</span>
										{#if r.vector_score != null}
											<span class="text-accent/80">vec {r.vector_score.toFixed(3)}</span>
										{/if}
										{#if r.bm25_score != null}
											<span class="text-warning/80">bm25 {r.bm25_score.toFixed(3)}</span>
										{/if}
										<span class="text-success/80">rrf {r.fused_score.toFixed(5)}</span>
									</span>
								</div>
								<pre class="px-3 py-2 whitespace-pre-wrap font-mono leading-relaxed text-text-dim text-[11px]">{r.content}</pre>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
