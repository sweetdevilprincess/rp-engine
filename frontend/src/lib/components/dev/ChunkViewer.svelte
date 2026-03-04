<script lang="ts">
	import { onMount } from 'svelte';
	import { listCards } from '$lib/api/cards';
	import { getVectorStats, listChunks, getChunksForFile, searchDebug } from '$lib/api/vectors';
	import type { StoryCardSummary, ChunkRow, VectorStats, DebugSearchResult } from '$lib/types';

	const tabs = [
		{ id: 'cards',  label: 'Card → Chunks' },
		{ id: 'browse', label: 'Chunk Browser'  },
		{ id: 'query',  label: 'Query Tester'   },
	];

	let activeTab = 'cards';

	// Stats
	let stats: VectorStats | null = null;
	let statsError = '';

	// Card → Chunks tab
	let cards: StoryCardSummary[] = [];
	let selectedCard: StoryCardSummary | null = null;
	let selectedChunks: ChunkRow[] = [];
	let chunksLoading = false;
	let chunksError = '';
	let cardsLoading = true;

	// Chunk Browser tab
	let allChunks: ChunkRow[] = [];
	let browseLoading = false;
	let browseError = '';
	let browseSearch = '';
	let browseTypeFilter = '';
	let browseLoaded = false;

	// Query Tester tab
	let queryText = '';
	let queryResults: DebugSearchResult[] = [];
	let queryLoading = false;
	let queryError = '';
	let queryRan = false;

	onMount(async () => {
		// Load stats
		try {
			stats = await getVectorStats();
		} catch (e: any) {
			statsError = e.message;
		}

		// Load card list
		try {
			const res = await listCards();
			cards = res.cards;
		} catch (e: any) {
			chunksError = e.message;
		} finally {
			cardsLoading = false;
		}
	});

	async function selectCard(card: StoryCardSummary) {
		if (selectedCard?.file_path === card.file_path) return;
		selectedCard = card;
		selectedChunks = [];
		chunksError = '';
		chunksLoading = true;
		try {
			selectedChunks = await getChunksForFile(card.file_path);
		} catch (e: any) {
			chunksError = e.message;
		} finally {
			chunksLoading = false;
		}
	}

	async function loadBrowse() {
		if (browseLoaded) return;
		browseLoading = true;
		browseError = '';
		try {
			allChunks = await listChunks({ limit: 500 });
			browseLoaded = true;
		} catch (e: any) {
			browseError = e.message;
		} finally {
			browseLoading = false;
		}
	}

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

	function handleTabClick(id: string) {
		activeTab = id;
		if (id === 'browse') loadBrowse();
	}

	$: filteredChunks = allChunks.filter((c) => {
		const matchSearch = !browseSearch || c.content.toLowerCase().includes(browseSearch.toLowerCase());
		const matchType = !browseTypeFilter || c.card_type === browseTypeFilter;
		return matchSearch && matchType;
	});

	$: browseTypes = [...new Set(allChunks.map((c) => c.card_type).filter(Boolean))] as string[];

	function embadgeColor(result: DebugSearchResult) {
		if (result.found_by === 'both')   return 'bg-success/20 text-success';
		if (result.found_by === 'vector') return 'bg-accent/20 text-accent';
		return 'bg-warning/20 text-warning';
	}

	function shortPath(fp: string | null): string {
		if (!fp) return '—';
		const parts = fp.replace(/\\/g, '/').split('/');
		return parts[parts.length - 1].replace('.md', '');
	}
</script>

<div class="space-y-3">
	<!-- Stats bar -->
	{#if stats}
		<div class="flex items-center gap-4 text-xs text-text-dim bg-surface border border-border-custom rounded-lg px-4 py-2">
			<span><span class="text-text font-medium">{stats.total_chunks}</span> chunks</span>
			<span>·</span>
			<span><span class="text-text font-medium">{stats.total_files}</span> files</span>
			<span>·</span>
			<span>
				<span class="text-text font-medium">{stats.chunks_with_embeddings}</span>
				/ {stats.total_chunks} embedded
			</span>
			<span>·</span>
			<span>avg <span class="text-text font-medium">{stats.avg_chunk_size}</span> chars</span>
			{#if stats.cards_without_vectors.length}
				<span>·</span>
				<span class="text-warning">{stats.cards_without_vectors.length} cards missing vectors</span>
			{/if}
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
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
					on:click={() => handleTabClick(tab.id)}
				>
					{tab.label}
				</button>
			{/each}
		</div>

		<!-- Card → Chunks -->
		{#if activeTab === 'cards'}
			<div class="flex" style="min-height: 360px;">
				<!-- Card list -->
				<div class="w-64 border-r border-border-custom flex flex-col">
					<div class="px-3 py-2 text-xs text-text-dim border-b border-border-custom">
						{cards.length} cards indexed
					</div>
					<div class="overflow-y-auto flex-1">
						{#if cardsLoading}
							<div class="p-3 space-y-1.5">
								{#each [1,2,3,4,5] as _}
									<div class="h-7 bg-surface2 rounded animate-pulse"></div>
								{/each}
							</div>
						{:else if chunksError && cards.length === 0}
							<div class="p-3 text-xs text-error">{chunksError}</div>
						{:else if cards.length === 0}
							<div class="p-3 text-xs text-text-dim">No cards indexed yet.</div>
						{:else}
							{#each cards as card}
								<button
									class="w-full text-left px-3 py-2 text-sm border-b border-border-custom/50
										hover:bg-surface2 transition-colors flex items-center justify-between gap-2
										{selectedCard?.file_path === card.file_path ? 'bg-accent/10 text-accent' : 'text-text-dim'}"
									on:click={() => selectCard(card)}
								>
									<span class="truncate">{card.name}</span>
									<span class="text-xs opacity-50 shrink-0">{card.card_type}</span>
								</button>
							{/each}
						{/if}
					</div>
				</div>

				<!-- Chunk display -->
				<div class="flex-1 overflow-y-auto p-4">
					{#if !selectedCard}
						<div class="h-full flex items-center justify-center text-sm text-text-dim">
							Select a card to see its chunks
						</div>
					{:else if chunksLoading}
						<div class="space-y-2">
							{#each [1,2,3] as _}
								<div class="h-24 bg-surface2 rounded-md animate-pulse"></div>
							{/each}
						</div>
					{:else if chunksError}
						<div class="text-sm text-error">{chunksError}</div>
					{:else if selectedChunks.length === 0}
						<div class="text-sm text-text-dim text-center py-8">No chunks found for this card.</div>
					{:else}
						<div class="space-y-3">
							<div class="text-xs text-text-dim flex items-center gap-3">
								<span class="font-medium text-text">{selectedCard.name}</span>
								<span>·</span>
								<span>{selectedChunks.length} chunk{selectedChunks.length !== 1 ? 's' : ''}</span>
								<span>·</span>
								<span>{selectedChunks.filter(c => c.has_embedding).length} embedded</span>
							</div>
							{#each selectedChunks as chunk}
								<div class="border border-border-custom rounded-md overflow-hidden text-xs">
									<div class="flex items-center gap-3 px-3 py-1.5 bg-surface2 border-b border-border-custom text-text-dim">
										<span class="font-mono">chunk {chunk.chunk_index + 1} / {chunk.total_chunks}</span>
										<span>·</span>
										<span>{chunk.content.length} chars</span>
										<span>·</span>
										<span class="{chunk.has_embedding ? 'text-success' : 'text-warning'}">
											{chunk.has_embedding ? '✓ embedded' : '⚠ no embedding'}
										</span>
									</div>
									<pre class="p-3 whitespace-pre-wrap font-mono leading-relaxed text-text-dim overflow-x-auto">{chunk.content}</pre>
								</div>
							{/each}
						</div>
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
						class="flex-1 bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm
							text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
					/>
					<select
						bind:value={browseTypeFilter}
						class="bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text-dim"
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
							<div class="h-14 bg-surface2 rounded animate-pulse"></div>
						{/each}
					</div>
				{:else if browseError}
					<div class="text-sm text-error">{browseError}</div>
				{:else if filteredChunks.length === 0}
					<div class="text-sm text-text-dim text-center py-8">
						{browseLoaded ? 'No chunks match filters.' : 'Loading...'}
					</div>
				{:else}
					<div class="text-xs text-text-dim mb-1">{filteredChunks.length} chunks</div>
					<div class="space-y-1.5 max-h-[480px] overflow-y-auto">
						{#each filteredChunks as chunk}
							<div class="border border-border-custom rounded-md text-xs overflow-hidden">
								<div class="flex items-center gap-2 px-3 py-1.5 bg-surface2 text-text-dim">
									<span class="font-medium text-text truncate">{shortPath(chunk.file_path)}</span>
									<span class="text-text-dim/50">·</span>
									<span>{chunk.card_type ?? '—'}</span>
									<span class="text-text-dim/50">·</span>
									<span>#{chunk.chunk_index}</span>
									<span class="ml-auto {chunk.has_embedding ? 'text-success' : 'text-warning'}">
										{chunk.has_embedding ? '✓' : '⚠'}
									</span>
								</div>
								<p class="px-3 py-2 text-text-dim line-clamp-2 font-mono leading-relaxed">{chunk.content}</p>
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
						on:keydown={(e) => e.key === 'Enter' && runQuery()}
						class="flex-1 bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm
							text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
					/>
					<button
						on:click={runQuery}
						disabled={queryLoading || !queryText.trim()}
						class="bg-accent text-white text-sm font-medium py-2 px-4 rounded-md
							hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
					>
						{queryLoading ? '...' : 'Search'}
					</button>
				</div>

				<div class="text-xs text-text-dim bg-surface2 rounded-md px-3 py-2">
					chunk_size=1000 · overlap=200 · cosine×0.7 + BM25×0.3 → RRF(k=60) · threshold=0.7
				</div>

				{#if queryError}
					<div class="text-sm text-error">{queryError}</div>
				{:else if queryLoading}
					<div class="space-y-2">
						{#each [1,2,3] as _}
							<div class="h-20 bg-surface2 rounded animate-pulse"></div>
						{/each}
					</div>
				{:else if queryRan && queryResults.length === 0}
					<div class="text-sm text-text-dim text-center py-8">No results above threshold.</div>
				{:else if queryResults.length > 0}
					<div class="space-y-2 max-h-[480px] overflow-y-auto">
						{#each queryResults as r, i}
							<div class="border border-border-custom rounded-md text-xs overflow-hidden">
								<div class="flex items-center gap-2 px-3 py-1.5 bg-surface2 text-text-dim flex-wrap">
									<span class="text-text font-medium">#{i + 1}</span>
									<span class="truncate max-w-[160px]">{shortPath(r.file_path)}</span>
									<span class="text-text-dim/50">·</span>
									<span>{r.card_type ?? '—'}</span>
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
