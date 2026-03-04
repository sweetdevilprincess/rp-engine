<script lang="ts">
	import { onMount } from 'svelte';
	import { activeRP } from '$lib/stores/rp';
	import { addToast } from '$lib/stores/ui';
	import { getGuidelines } from '$lib/api/context';
	import { listCards } from '$lib/api/cards';
	import { listThreads } from '$lib/api/threads';
	import type { GuidelinesResponse, StoryCardSummary, ThreadDetail } from '$lib/types';
	import { CARD_TYPES } from '$lib/types/enums';

	// ── Data ─────────────────────────────────────────────────
	let guidelines: GuidelinesResponse | null = null;
	let cardCounts: Record<string, number> = {};
	let totalCards = 0;
	let chapters: StoryCardSummary[] = [];
	let threads: ThreadDetail[] = [];
	let loading = false;

	// ── Right panel state ─────────────────────────────────────
	let activeTab: 'chapters' | 'threads' = 'chapters';
	let expandedChapter: StoryCardSummary | null = null;
	let expandedThread: string | null = null;

	onMount(async () => {
		if (!$activeRP) return;
		loading = true;
		try {
			const [gl, allCards, threadRes, chapterRes] = await Promise.all([
				getGuidelines($activeRP.rp_folder).catch(() => null),
				listCards().catch(() => ({ cards: [], total: 0 })),
				listThreads().catch(() => ({ threads: [], total: 0 })),
				listCards({ card_type: 'chapter_summary' }).catch(() => ({ cards: [], total: 0 })),
			]);

			guidelines = gl;
			totalCards = allCards.total;
			cardCounts = allCards.cards.reduce((acc, c) => {
				acc[c.card_type] = (acc[c.card_type] ?? 0) + 1;
				return acc;
			}, {} as Record<string, number>);
			threads = threadRes.threads;
			chapters = chapterRes.cards;
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load RP data', 'error');
		} finally {
			loading = false;
		}
	});

	// ── Helpers ───────────────────────────────────────────────
	function toneArray(tone: string[] | string | null): string[] {
		if (!tone) return [];
		return Array.isArray(tone) ? tone : [tone];
	}

	function nextThreshold(thread: ThreadDetail): { label: string; value: number } | null {
		const entries = Object.entries(thread.thresholds)
			.map(([k, v]) => ({ label: k, value: v }))
			.sort((a, b) => a.value - b.value);
		return entries.find(e => e.value > thread.current_counter) ?? entries[entries.length - 1] ?? null;
	}

	function threadProgress(thread: ThreadDetail): number {
		const next = nextThreshold(thread);
		if (!next || next.value === 0) return 0;
		return Math.min(100, (thread.current_counter / next.value) * 100);
	}

	function priorityStyle(p: string | null) {
		if (p === 'plot_critical') return 'bg-error/20 text-error';
		if (p === 'important') return 'bg-warning/20 text-warning';
		return 'bg-surface2 text-text-dim';
	}

	function statusStyle(s: string) {
		if (s === 'active') return 'bg-success/20 text-success';
		if (s === 'dormant') return 'bg-warning/20 text-warning';
		return 'bg-surface2 text-text-dim';
	}

	function progressColor(pct: number) {
		if (pct >= 80) return '#ef5350';
		if (pct >= 50) return '#ffa726';
		return '#7c6fe0';
	}

	const typeLabel: Record<string, string> = {
		npc: 'NPCs', character: 'Characters', location: 'Locations',
		memory: 'Memories', secret: 'Secrets', knowledge: 'Knowledge',
		organization: 'Organizations', plot_thread: 'Plot Threads',
		plot_arc: 'Plot Arcs', chapter_summary: 'Chapters',
		item: 'Items', lore: 'Lore',
	};

	$: activeThreads   = threads.filter(t => t.status === 'active');
	$: dormantThreads  = threads.filter(t => t.status === 'dormant');
	$: resolvedThreads = threads.filter(t => t.status === 'resolved');
</script>

<div class="flex gap-6">

	<!-- ── Left: Story Bible + Card Health ──────────────────── -->
	<aside class="w-80 shrink-0 space-y-4 self-start">

		<!-- RP header -->
		<div class="bg-surface rounded-lg border border-border-custom px-4 py-3">
			<h1 class="text-lg font-bold text-text">{$activeRP?.rp_folder ?? 'RP Overview'}</h1>
			<p class="text-xs text-text-dim mt-0.5">{totalCards} story card{totalCards !== 1 ? 's' : ''}</p>
		</div>

		<!-- Guidelines (Story Bible) -->
		{#if guidelines}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-2.5 border-b border-border-custom">
					<h2 class="text-xs font-semibold text-text-dim uppercase tracking-wider">Story Bible</h2>
				</div>
				<div class="px-4 py-3 space-y-2 text-sm">
					{#if guidelines.pov_character}
						<div class="flex justify-between">
							<span class="text-text-dim">POV Character</span>
							<span class="text-text font-medium">{guidelines.pov_character}</span>
						</div>
					{/if}
					{#if guidelines.pov_mode}
						<div class="flex justify-between">
							<span class="text-text-dim">POV Mode</span>
							<span class="text-text capitalize">{guidelines.pov_mode}</span>
						</div>
					{/if}
					{#if guidelines.narrative_voice}
						<div class="flex justify-between">
							<span class="text-text-dim">Narrative Voice</span>
							<span class="text-text capitalize">{guidelines.narrative_voice} person</span>
						</div>
					{/if}
					{#if guidelines.tense}
						<div class="flex justify-between">
							<span class="text-text-dim">Tense</span>
							<span class="text-text capitalize">{guidelines.tense}</span>
						</div>
					{/if}
					{#if guidelines.scene_pacing}
						<div class="flex justify-between">
							<span class="text-text-dim">Pacing</span>
							<span class="text-text capitalize">{guidelines.scene_pacing}</span>
						</div>
					{/if}
					{#if guidelines.response_length}
						<div class="flex justify-between">
							<span class="text-text-dim">Response Length</span>
							<span class="text-text capitalize">{guidelines.response_length}</span>
						</div>
					{/if}
					{#if toneArray(guidelines.tone).length}
						<div>
							<span class="text-text-dim block mb-1">Tone</span>
							<div class="flex flex-wrap gap-1">
								{#each toneArray(guidelines.tone) as t}
									<span class="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{t}</span>
								{/each}
							</div>
						</div>
					{/if}
					{#if guidelines.sensitive_themes?.length}
						<div>
							<span class="text-text-dim block mb-1">Sensitive Themes</span>
							<div class="flex flex-wrap gap-1">
								{#each guidelines.sensitive_themes as theme}
									<span class="text-xs bg-warning/10 text-warning px-1.5 py-0.5 rounded">{theme}</span>
								{/each}
							</div>
						</div>
					{/if}
					{#if guidelines.dual_characters?.length}
						<div>
							<span class="text-text-dim block mb-1">Dual Characters</span>
							<div class="flex flex-wrap gap-1">
								{#each guidelines.dual_characters as c}
									<span class="text-xs bg-surface2 text-text px-1.5 py-0.5 rounded">{c}</span>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			</div>
		{:else if !loading}
			<div class="bg-surface rounded-lg border border-border-custom px-4 py-3 text-sm text-text-dim">
				No guidelines found. Create a <code class="text-xs font-mono">guidelines.md</code> in the RP folder.
			</div>
		{/if}

		<!-- Card health -->
		<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
			<div class="px-4 py-2.5 border-b border-border-custom">
				<h2 class="text-xs font-semibold text-text-dim uppercase tracking-wider">Card Library</h2>
			</div>
			{#if loading}
				<div class="px-4 py-3 text-sm text-text-dim">Loading...</div>
			{:else if totalCards === 0}
				<div class="px-4 py-3 text-sm text-text-dim">No story cards indexed yet.</div>
			{:else}
				<div class="divide-y divide-border-custom">
					{#each CARD_TYPES as type}
						{#if cardCounts[type]}
							<div class="flex items-center justify-between px-4 py-2 text-sm">
								<span class="text-text-dim">{typeLabel[type] ?? type}</span>
								<span class="text-text font-medium tabular-nums">{cardCounts[type]}</span>
							</div>
						{/if}
					{/each}
				</div>
			{/if}
		</div>
	</aside>

	<!-- ── Right: Chapters / Plot Threads ───────────────────── -->
	<div class="flex-1 min-w-0 space-y-3">

		<!-- Tab switcher + back button -->
		<div class="flex items-center gap-2">
			{#if expandedChapter}
				<button
					class="flex items-center gap-1.5 text-sm text-text-dim hover:text-text transition-colors mr-2"
					on:click={() => (expandedChapter = null)}
				>
					<svg class="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M10 4L6 8l4 4" />
					</svg>
					Back
				</button>
			{/if}
			<div class="flex bg-surface border border-border-custom rounded-lg overflow-hidden">
				<button
					class="px-4 py-2 text-sm transition-colors
						{activeTab === 'chapters'
							? 'bg-accent/10 text-accent font-medium'
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
					on:click={() => { activeTab = 'chapters'; expandedChapter = null; }}
				>Chapters</button>
				<button
					class="px-4 py-2 text-sm border-l border-border-custom transition-colors
						{activeTab === 'threads'
							? 'bg-accent/10 text-accent font-medium'
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
					on:click={() => { activeTab = 'threads'; expandedChapter = null; }}
				>Plot Threads</button>
			</div>
			{#if activeTab === 'chapters'}
				<span class="text-xs text-text-dim">{chapters.length} chapter{chapters.length !== 1 ? 's' : ''}</span>
			{:else}
				<span class="text-xs text-text-dim">{activeThreads.length} active</span>
			{/if}
		</div>

		<!-- ── Chapters ─────────────────────────────────────── -->
		{#if activeTab === 'chapters'}
			{#if expandedChapter}
				<!-- Full chapter view -->
				<div class="bg-surface rounded-lg border border-border-custom p-5">
					<h2 class="text-base font-semibold text-text mb-3">{expandedChapter.name}</h2>
					{#if expandedChapter.summary}
						<p class="text-sm text-text whitespace-pre-wrap leading-relaxed">{expandedChapter.summary}</p>
					{:else}
						<p class="text-sm text-text-dim">No content preview available.</p>
					{/if}
				</div>
			{:else if chapters.length === 0}
				<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
					{loading ? 'Loading chapters...' : 'No chapter summaries yet.'}
				</div>
			{:else}
				<div class="space-y-2">
					{#each chapters as chapter, i}
						<button
							class="w-full bg-surface rounded-lg border border-border-custom p-4 text-left
								hover:border-accent/40 hover:bg-surface2/50 transition-colors"
							on:click={() => (expandedChapter = chapter)}
						>
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="flex items-center gap-2 mb-1">
										<span class="text-xs text-text-dim font-mono">Ch. {i + 1}</span>
										{#if chapter.tags?.length}
											{#each chapter.tags.slice(0, 2) as tag}
												<span class="text-xs bg-surface2 text-text-dim px-1.5 py-0.5 rounded">{tag}</span>
											{/each}
										{/if}
									</div>
									<p class="text-sm font-medium text-text">{chapter.name}</p>
									{#if chapter.summary}
										<p class="text-xs text-text-dim mt-1 line-clamp-2">{chapter.summary}</p>
									{/if}
								</div>
								<svg class="w-4 h-4 text-text-dim shrink-0 mt-0.5" viewBox="0 0 16 16" fill="none"
									stroke="currentColor" stroke-width="2">
									<path d="M6 4l4 4-4 4" />
								</svg>
							</div>
						</button>
					{/each}
				</div>
			{/if}

		<!-- ── Plot Threads ──────────────────────────────────── -->
		{:else}
			{#if loading}
				<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
					Loading threads...
				</div>
			{:else if threads.length === 0}
				<div class="bg-surface rounded-lg border border-border-custom p-8 text-center text-sm text-text-dim">
					No plot threads found.
				</div>
			{:else}
				<div class="space-y-4">
					<!-- Active threads -->
					{#if activeThreads.length}
						<div class="space-y-2">
							<p class="text-xs font-semibold text-text-dim uppercase tracking-wider px-1">Active</p>
							{#each activeThreads as thread}
								{@const pct = threadProgress(thread)}
								{@const next = nextThreshold(thread)}
								<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
									<button
										class="w-full flex items-start gap-3 px-4 py-3 hover:bg-surface2 transition-colors text-left"
										on:click={() => (expandedThread = expandedThread === thread.thread_id ? null : thread.thread_id)}
									>
										<div class="flex-1 min-w-0 space-y-2">
											<div class="flex items-center gap-2 flex-wrap">
												<span class="text-sm font-medium text-text">{thread.name}</span>
												{#if thread.priority}
													<span class="text-xs px-1.5 py-0.5 rounded {priorityStyle(thread.priority)}">{thread.priority.replace('_', ' ')}</span>
												{/if}
												{#if thread.thread_type}
													<span class="text-xs bg-surface2 text-text-dim px-1.5 py-0.5 rounded">{thread.thread_type}</span>
												{/if}
											</div>
											<!-- Progress bar -->
											<div class="flex items-center gap-2">
												<div class="flex-1 h-1.5 bg-surface2 rounded-full overflow-hidden">
													<div class="h-full rounded-full transition-all"
														style="width:{pct}%;background:{progressColor(pct)}"></div>
												</div>
												<span class="text-xs text-text-dim shrink-0 font-mono">
													{thread.current_counter}{next ? `/${next.value}` : ''}
												</span>
											</div>
										</div>
										<svg class="w-4 h-4 text-text-dim shrink-0 mt-0.5 transition-transform
												{expandedThread === thread.thread_id ? 'rotate-180' : ''}"
											viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
											<path d="M4 6l4 4 4-4" />
										</svg>
									</button>

									{#if expandedThread === thread.thread_id}
										<div class="border-t border-border-custom px-4 py-3 space-y-3 text-sm">
											{#if thread.related_characters?.length}
												<div>
													<p class="text-xs text-text-dim mb-1">Related Characters</p>
													<div class="flex flex-wrap gap-1">
														{#each thread.related_characters as c}
															<span class="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">{c}</span>
														{/each}
													</div>
												</div>
											{/if}
											{#if thread.keywords?.length}
												<div>
													<p class="text-xs text-text-dim mb-1">Keywords</p>
													<div class="flex flex-wrap gap-1">
														{#each thread.keywords as kw}
															<span class="text-xs bg-surface2 text-text-dim px-1.5 py-0.5 rounded">{kw}</span>
														{/each}
													</div>
												</div>
											{/if}
											{#if Object.keys(thread.consequences).length}
												<div>
													<p class="text-xs text-text-dim mb-1">Consequences</p>
													<div class="space-y-1">
														{#each Object.entries(thread.consequences) as [level, text]}
															<div class="flex gap-2 text-xs">
																<span class="text-text-dim shrink-0 font-mono">{level}:</span>
																<span class="text-text">{text}</span>
															</div>
														{/each}
													</div>
												</div>
											{/if}
										</div>
									{/if}
								</div>
							{/each}
						</div>
					{/if}

					<!-- Dormant threads -->
					{#if dormantThreads.length}
						<div class="space-y-2">
							<p class="text-xs font-semibold text-text-dim uppercase tracking-wider px-1">Dormant</p>
							{#each dormantThreads as thread}
								<div class="bg-surface rounded-lg border border-border-custom px-4 py-2.5 flex items-center gap-3">
									<span class="text-sm text-text-dim">{thread.name}</span>
									{#if thread.priority}
										<span class="text-xs px-1.5 py-0.5 rounded {priorityStyle(thread.priority)}">{thread.priority.replace('_', ' ')}</span>
									{/if}
									<span class="text-xs text-text-dim ml-auto font-mono">#{thread.current_counter}</span>
								</div>
							{/each}
						</div>
					{/if}

					<!-- Resolved threads (collapsed) -->
					{#if resolvedThreads.length}
						<details class="bg-surface rounded-lg border border-border-custom overflow-hidden">
							<summary class="flex items-center justify-between px-4 py-2.5 cursor-pointer
								hover:bg-surface2 transition-colors list-none text-sm text-text-dim">
								<span>Resolved ({resolvedThreads.length})</span>
								<svg class="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M4 6l4 4 4-4" />
								</svg>
							</summary>
							<div class="border-t border-border-custom divide-y divide-border-custom">
								{#each resolvedThreads as thread}
									<div class="px-4 py-2 flex items-center gap-2 text-sm text-text-dim">
										<span class="line-through">{thread.name}</span>
										<span class="text-xs bg-success/10 text-success px-1.5 py-0.5 rounded ml-auto">resolved</span>
									</div>
								{/each}
							</div>
						</details>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>
