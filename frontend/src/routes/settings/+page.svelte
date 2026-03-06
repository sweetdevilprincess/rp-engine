<script lang="ts">
	import { onMount } from 'svelte';
	import { getConfig, updateConfig, getActiveRP, setActiveRP, type AppConfig } from '$lib/api/config';
	import { checkHealth, type HealthResponse } from '$lib/api/health';
	import { getVectorStats, reindexExchanges } from '$lib/api/vectors';
	import { reindex } from '$lib/api/cards';
	import { addToast } from '$lib/stores/ui';
	import type { VectorStats, ReindexResponse } from '$lib/types';
	import Card from '$lib/components/ui/Card.svelte';
	import Btn from '$lib/components/ui/Btn.svelte';
	import InputField from '$lib/components/ui/InputField.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';
	import SideNav from '$lib/components/ui/SideNav.svelte';

	const sections = [
		{ id: 'general',     label: 'General'        },
		{ id: 'appearance',  label: 'Appearance'     },
		{ id: 'system',      label: 'System'         },
		{ id: 'maintenance', label: 'Maintenance'    },
		{ id: 'server',      label: 'Server'         },
		{ id: 'llm',         label: 'LLM Models'     },
		{ id: 'search',      label: 'Search Tuning'  },
		{ id: 'trust',       label: 'Trust Tuning'   },
		{ id: 'context',     label: 'Context Tuning' },
		{ id: 'apikeys',     label: 'API Keys'       },
	];

	let activeSection = 'general';
	let loadError = '';
	let saveStatus: Record<string, 'idle' | 'saving' | 'saved' | 'error'> = {};

	// Server
	let serverHost = '0.0.0.0';
	let serverPort = 3000;

	// LLM
	let llmNpcReactions = 'anthropic/claude-haiku';
	let llmAnalysis     = 'google/gemini-2.0-flash-001';
	let llmCardGen      = 'google/gemini-2.0-flash-001';
	let llmEmbeddings   = 'openai/text-embedding-3-small';
	let llmFallback     = 'google/gemini-2.0-flash-001';
	let llmDefaultPov   = 'Lilith';

	// Search
	let searchVectorWeight = 0.7;
	let searchBm25Weight   = 0.3;
	let searchThreshold    = 0.7;
	let searchChunkSize    = 1000;
	let searchChunkOverlap = 200;

	// Trust
	let trustIncrease    = 1;
	let trustDecrease    = 2;
	let trustSessionGain = 8;
	let trustSessionLoss = -15;
	let trustMin         = -50;
	let trustMax         = 50;

	// Context
	let contextMaxDocs    = 5;
	let contextMaxHops    = 2;
	let contextStaleAfter = 8;

	// Active RP
	let activeRP = false;
	let activeRPSessions = 0;
	let activeRPToggling = false;

	// API Keys
	let openrouterKey = '';
	let keyVisible = false;

	// Appearance (stored in localStorage)
	let accentColor = '#6d8c5e';
	let fontSize: 'small' | 'medium' | 'large' = 'medium';
	let uiDensity: 'compact' | 'comfortable' | 'spacious' = 'comfortable';

	const ACCENT_PRESETS = [
		{ label: 'Sage',   color: '#6d8c5e' },
		{ label: 'Copper', color: '#c4956a' },
		{ label: 'Gold',   color: '#b89f6a' },
		{ label: 'Berry',  color: '#8b6fc0' },
		{ label: 'Rose',   color: '#b85c55' },
		{ label: 'Steel',  color: '#5e82a8' },
	];

	function loadAppearance() {
		try {
			const stored = localStorage.getItem('rp-appearance');
			if (stored) {
				const parsed = JSON.parse(stored);
				accentColor = parsed.accentColor ?? accentColor;
				fontSize = parsed.fontSize ?? fontSize;
				uiDensity = parsed.uiDensity ?? uiDensity;
			}
		} catch {}
	}

	function saveAppearance() {
		const prefs = { accentColor, fontSize, uiDensity };
		localStorage.setItem('rp-appearance', JSON.stringify(prefs));
		applyAppearance();
		addToast('Appearance saved', 'success');
	}

	function applyAppearance() {
		const root = document.documentElement;
		root.style.setProperty('--color-accent', accentColor);

		const fontSizes: Record<string, string> = { small: '13px', medium: '14px', large: '16px' };
		root.style.setProperty('font-size', fontSizes[fontSize] ?? '14px');

		const densityScale: Record<string, string> = { compact: '0.85', comfortable: '1', spacious: '1.2' };
		root.style.setProperty('--density-scale', densityScale[uiDensity] ?? '1');
	}

	// System Info
	let health: HealthResponse | null = null;
	let configData: AppConfig | null = null;

	// Maintenance
	let vectorStats: VectorStats | null = null;
	let vectorStatsLoading = false;
	let reindexing = false;
	let reembedding = false;

	onMount(async () => {
		loadAppearance();
		try {
			const [cfg, rpStatus, h] = await Promise.all([getConfig(), getActiveRP(), checkHealth()]);
			configData = cfg;
			health = h;
			activeRP = rpStatus.active_rp;
			activeRPSessions = rpStatus.session_count;
			serverHost         = cfg.server.host;
			serverPort         = cfg.server.port;
			llmNpcReactions    = cfg.llm.models.npc_reactions;
			llmAnalysis        = cfg.llm.models.response_analysis;
			llmCardGen         = cfg.llm.models.card_generation;
			llmEmbeddings      = cfg.llm.models.embeddings;
			llmFallback        = cfg.llm.fallback_model;
			llmDefaultPov      = cfg.rp.default_pov_character;
			searchVectorWeight = cfg.search.vector_weight;
			searchBm25Weight   = cfg.search.bm25_weight;
			searchThreshold    = cfg.search.similarity_threshold;
			searchChunkSize    = cfg.search.chunk_size;
			searchChunkOverlap = cfg.search.chunk_overlap;
			trustIncrease      = cfg.trust.increase_value;
			trustDecrease      = cfg.trust.decrease_value;
			trustSessionGain   = cfg.trust.session_max_gain;
			trustSessionLoss   = cfg.trust.session_max_loss;
			trustMin           = cfg.trust.min_score;
			trustMax           = cfg.trust.max_score;
			contextMaxDocs     = cfg.context.max_documents;
			contextMaxHops     = cfg.context.max_graph_hops;
			contextStaleAfter  = cfg.context.stale_threshold_turns;
		} catch (e: any) {
			loadError = e.message;
		}
	});

	async function loadVectorStats() {
		vectorStatsLoading = true;
		try {
			vectorStats = await getVectorStats();
		} catch (e: any) {
			addToast(`Failed to load vector stats: ${e.message}`, 'error');
		} finally {
			vectorStatsLoading = false;
		}
	}

	async function handleReindex() {
		reindexing = true;
		try {
			const result: ReindexResponse = await reindex();
			addToast(`Reindexed ${result.entities} entities, ${result.connections} connections in ${result.duration_ms}ms`, 'success');
		} catch (e: any) {
			addToast(`Reindex failed: ${e.message}`, 'error');
		} finally {
			reindexing = false;
		}
	}

	async function handleReembed() {
		reembedding = true;
		try {
			const result = await reindexExchanges();
			addToast(`Re-embedded ${result.embedded}/${result.total_exchanges} exchanges (${result.failed} failed)`, 'success');
		} catch (e: any) {
			addToast(`Re-embed failed: ${e.message}`, 'error');
		} finally {
			reembedding = false;
		}
	}

	async function save(section: string, body: Record<string, unknown>) {
		saveStatus[section] = 'saving';
		try {
			await updateConfig({ [section]: body });
			saveStatus[section] = 'saved';
			setTimeout(() => { saveStatus[section] = 'idle'; }, 2000);
		} catch {
			saveStatus[section] = 'error';
			setTimeout(() => { saveStatus[section] = 'idle'; }, 3000);
		}
	}

	function saveServer() {
		save('server', { host: serverHost, port: serverPort });
	}
	function saveLlm() {
		save('llm', {
			models: {
				npc_reactions: llmNpcReactions,
				response_analysis: llmAnalysis,
				card_generation: llmCardGen,
				embeddings: llmEmbeddings,
			},
			fallback_model: llmFallback,
		});
		save('rp', { default_pov_character: llmDefaultPov });
	}
	function saveSearch() {
		save('search', {
			vector_weight: searchVectorWeight,
			bm25_weight: searchBm25Weight,
			similarity_threshold: searchThreshold,
			chunk_size: searchChunkSize,
			chunk_overlap: searchChunkOverlap,
		});
	}
	function saveTrust() {
		save('trust', {
			increase_value: trustIncrease,
			decrease_value: trustDecrease,
			session_max_gain: trustSessionGain,
			session_max_loss: trustSessionLoss,
			min_score: trustMin,
			max_score: trustMax,
		});
	}
	function saveContext() {
		save('context', {
			max_documents: contextMaxDocs,
			max_graph_hops: contextMaxHops,
			stale_threshold_turns: contextStaleAfter,
		});
	}
	async function toggleActiveRP() {
		activeRPToggling = true;
		try {
			const result = await setActiveRP(!activeRP);
			activeRP = result.active_rp;
			activeRPSessions = result.session_count;
		} catch {
			// revert on failure
		} finally {
			activeRPToggling = false;
		}
	}

	async function saveApiKey() {
		if (!openrouterKey.trim()) return;
		saveStatus['apikeys'] = 'saving';
		try {
			await updateConfig({ openrouter_api_key: openrouterKey.trim() });
			openrouterKey = '';
			saveStatus['apikeys'] = 'saved';
			setTimeout(() => { saveStatus['apikeys'] = 'idle'; }, 2000);
		} catch {
			saveStatus['apikeys'] = 'error';
			setTimeout(() => { saveStatus['apikeys'] = 'idle'; }, 3000);
		}
	}
</script>

<div class="flex gap-3">
	<SideNav title="Settings" items={sections} bind:active={activeSection} />

	<!-- Section content -->
	<div class="flex-1 min-w-0 max-w-2xl">

		{#if loadError}
			<div class="bg-error/10 border border-error/30 rounded-[10px] px-4 py-2.5 text-sm text-error mb-4">
				Failed to load config: {loadError}
			</div>
		{/if}

		<!-- General -->
		{#if activeSection === 'general'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">General</h2>
					<p class="text-xs text-text-dim mt-0.5">Global engine settings.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="flex items-center justify-between">
						<div>
							<p class="text-sm font-medium text-text">Active RP</p>
							<p class="text-xs text-text-dim mt-0.5">
								When disabled, chat exchanges are not auto-saved. Use this while editing the UI or testing to avoid polluting your chat logs.
							</p>
							{#if activeRPSessions > 0}
								<p class="text-xs text-text-dim mt-1">{activeRPSessions} active session{activeRPSessions !== 1 ? 's' : ''}</p>
							{/if}
						</div>
						<button
							onclick={toggleActiveRP}
							disabled={activeRPToggling}
							class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200
								focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg
								disabled:opacity-50 disabled:cursor-not-allowed
								{activeRP ? 'bg-accent' : 'bg-bg-subtle'}"
							role="switch"
							aria-checked={activeRP}
							aria-label="Toggle active RP auto-save"
						>
							<span
								class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform transition duration-200
									{activeRP ? 'translate-x-5' : 'translate-x-0'}"
							></span>
						</button>
					</div>
				</div>
			</Card>

		<!-- Appearance -->
		{:else if activeSection === 'appearance'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Appearance</h2>
					<p class="text-xs text-text-dim mt-0.5">Customize the look and feel. Saved per-browser.</p>
				</div>
				<div class="p-4 space-y-6">
					<!-- Accent Color -->
					<div>
						<p class="text-xs font-medium text-text-dim mb-2">Accent Color</p>
						<div class="flex items-center gap-2">
							{#each ACCENT_PRESETS as preset}
								<button
									class="w-8 h-8 rounded-full border-2 transition-all
										{accentColor === preset.color ? 'border-text scale-110' : 'border-transparent hover:border-border-custom'}"
									style="background: {preset.color}"
									onclick={() => (accentColor = preset.color)}
									title={preset.label}
								></button>
							{/each}
							<input
								type="color"
								bind:value={accentColor}
								class="w-8 h-8 rounded-full border border-border-custom cursor-pointer bg-transparent"
								title="Custom color"
							/>
							<span class="text-xs text-text-dim font-mono ml-2">{accentColor}</span>
						</div>
					</div>

					<!-- Font Size -->
					<div>
						<p class="text-xs font-medium text-text-dim mb-2">Font Size</p>
						<div class="flex gap-2">
							{#each [['small', 'Small'], ['medium', 'Medium'], ['large', 'Large']] as [value, label]}
								<button
									class="px-4 py-2 rounded-[10px] text-sm transition-all border
										{fontSize === value
											? 'bg-accent/15 text-accent border-accent/30'
											: 'bg-bg-subtle text-text-dim border-border-custom/50 hover:text-text hover:border-border-custom'}"
									onclick={() => (fontSize = value as typeof fontSize)}
								>{label}</button>
							{/each}
						</div>
					</div>

					<!-- UI Density -->
					<div>
						<p class="text-xs font-medium text-text-dim mb-2">UI Density</p>
						<div class="flex gap-2">
							{#each [['compact', 'Compact'], ['comfortable', 'Comfortable'], ['spacious', 'Spacious']] as [value, label]}
								<button
									class="px-4 py-2 rounded-[10px] text-sm transition-all border
										{uiDensity === value
											? 'bg-accent/15 text-accent border-accent/30'
											: 'bg-bg-subtle text-text-dim border-border-custom/50 hover:text-text hover:border-border-custom'}"
									onclick={() => (uiDensity = value as typeof uiDensity)}
								>{label}</button>
							{/each}
						</div>
					</div>

					<!-- Theme (placeholder) -->
					<div>
						<p class="text-xs font-medium text-text-dim mb-2">Theme</p>
						<div class="flex gap-2">
							<button class="px-4 py-2 rounded-[10px] text-sm bg-accent/15 text-accent border border-accent/30">Light</button>
							<button class="px-4 py-2 rounded-[10px] text-sm bg-bg-subtle text-text-dim/40 border border-border-custom/30 cursor-not-allowed" disabled title="Coming soon">Dark</button>
						</div>
					</div>

					<div class="flex items-center justify-end gap-3 pt-2 border-t border-border-custom">
						<Btn primary onclick={saveAppearance}>Apply & Save</Btn>
					</div>
				</div>
			</Card>

		<!-- System Info -->
		{:else if activeSection === 'system'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">System</h2>
					<p class="text-xs text-text-dim mt-0.5">Read-only server and database information.</p>
				</div>
				<div class="p-4 space-y-3">
					{@render infoRow('Server Version', health?.version ?? '...')}
					{@render infoRow('Indexed Cards', health?.indexed_cards != null ? String(health.indexed_cards) : '...')}
					{@render infoRow('Vault Root', configData?.paths.vault_root ?? '...')}
					{@render infoRow('Database Path', configData?.paths.db_path ?? '...')}
					<div>
						<p class="text-xs font-medium text-text-dim mb-1">CORS Origins</p>
						{#if configData?.server.cors_origins?.length}
							<div class="flex flex-wrap gap-1.5">
								{#each configData.server.cors_origins as origin}
									<span class="px-2 py-0.5 bg-bg-subtle border border-border-custom rounded text-xs text-text font-mono">{origin}</span>
								{/each}
							</div>
						{:else}
							<p class="text-sm text-text-dim">None configured</p>
						{/if}
					</div>
				</div>
			</Card>

		<!-- Maintenance -->
		{:else if activeSection === 'maintenance'}
			<div class="space-y-4">
				<!-- Vector Stats -->
				<Card>
					<div class="px-4 py-3 border-b border-border-custom flex items-center justify-between">
						<div>
							<h2 class="text-sm font-semibold text-text">Vector Stats</h2>
							<p class="text-xs text-text-dim mt-0.5">Embedding and chunk statistics for the vector store.</p>
						</div>
						<button
							onclick={loadVectorStats}
							disabled={vectorStatsLoading}
							class="text-xs text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
						>
							{vectorStatsLoading ? 'Loading...' : vectorStats ? 'Refresh' : 'Load Stats'}
						</button>
					</div>
					{#if vectorStats}
						<div class="p-4 grid grid-cols-2 gap-3">
							{@render statCell('Total Chunks', String(vectorStats.total_chunks))}
							{@render statCell('With Embeddings', String(vectorStats.chunks_with_embeddings))}
							{@render statCell('Without Embeddings', String(vectorStats.chunks_without_embeddings))}
							{@render statCell('Total Files', String(vectorStats.total_files))}
							{@render statCell('Avg Chunk Size', `${Math.round(vectorStats.avg_chunk_size)} chars`)}
							{@render statCell('Cards Without Vectors', String(vectorStats.cards_without_vectors.length))}
						</div>
						{#if vectorStats.cards_without_vectors.length > 0}
							<div class="px-4 pb-4">
								<p class="text-xs font-medium text-text-dim mb-1">Cards missing vectors:</p>
								<div class="flex flex-wrap gap-1">
									{#each vectorStats.cards_without_vectors as card}
										<span class="px-1.5 py-0.5 bg-warning/10 border border-warning/30 rounded text-xs text-warning">{card}</span>
									{/each}
								</div>
							</div>
						{/if}
					{:else if !vectorStatsLoading}
						<div class="p-4 text-sm text-text-dim">Click "Load Stats" to fetch vector store statistics.</div>
					{/if}
				</Card>

				<!-- Actions -->
				<Card>
					<div class="px-4 py-3 border-b border-border-custom">
						<h2 class="text-sm font-semibold text-text">Actions</h2>
						<p class="text-xs text-text-dim mt-0.5">Database maintenance operations.</p>
					</div>
					<div class="p-4 space-y-4">
						<div class="flex items-center justify-between">
							<div>
								<p class="text-sm font-medium text-text">Reindex Cards</p>
								<p class="text-xs text-text-dim mt-0.5">Re-scan all story card files and rebuild the index.</p>
							</div>
							<Btn primary small onclick={handleReindex} disabled={reindexing}>
								{reindexing ? 'Reindexing...' : 'Reindex'}
							</Btn>
						</div>
						<div class="border-t border-border-custom"></div>
						<div class="flex items-center justify-between">
							<div>
								<p class="text-sm font-medium text-text">Re-embed Exchanges</p>
								<p class="text-xs text-text-dim mt-0.5">Regenerate vector embeddings for all exchanges.</p>
							</div>
							<Btn primary small onclick={handleReembed} disabled={reembedding}>
								{reembedding ? 'Re-embedding...' : 'Re-embed'}
							</Btn>
						</div>
					</div>
				</Card>
			</div>

		<!-- Server -->
		{:else if activeSection === 'server'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Server</h2>
					<p class="text-xs text-text-dim mt-0.5">Changes to host or port require a server restart.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="host">Host</label>
							<InputField id="host" bind:value={serverHost} />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="port">Port</label>
							<input id="port" type="number" bind:value={serverPort} min="1024" max="65535"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('server', saveServer)}
				</div>
			</Card>

		<!-- LLM Models -->
		{:else if activeSection === 'llm'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">LLM Models</h2>
					<p class="text-xs text-text-dim mt-0.5">Model IDs passed to OpenRouter. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-npc">NPC Reactions</label>
						<InputField id="llm-npc" bind:value={llmNpcReactions} class="font-mono" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-analysis">Response Analysis</label>
						<InputField id="llm-analysis" bind:value={llmAnalysis} class="font-mono" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-cardgen">Card Generation</label>
						<InputField id="llm-cardgen" bind:value={llmCardGen} class="font-mono" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-embed">Embeddings</label>
						<InputField id="llm-embed" bind:value={llmEmbeddings} class="font-mono" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-fallback">Fallback Model</label>
						<InputField id="llm-fallback" bind:value={llmFallback} class="font-mono" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-pov">Default POV Character</label>
						<InputField id="llm-pov" bind:value={llmDefaultPov} />
					</div>
					{@render saveButton('llm', saveLlm)}
				</div>
			</Card>

		<!-- Search Tuning -->
		{:else if activeSection === 'search'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Search Tuning</h2>
					<p class="text-xs text-text-dim mt-0.5">Controls chunking and retrieval weights. Requires server restart to take effect. Chunk size changes also require reindexing.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-3 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="vec-weight">Vector Weight</label>
							<input id="vec-weight" type="number" bind:value={searchVectorWeight}
								min="0" max="1" step="0.05"
								class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="bm25-weight">BM25 Weight</label>
							<input id="bm25-weight" type="number" bind:value={searchBm25Weight}
								min="0" max="1" step="0.05"
								class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="threshold">Similarity Threshold</label>
							<input id="threshold" type="number" bind:value={searchThreshold}
								min="0" max="1" step="0.05"
								class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="chunk-size">Chunk Size (chars)</label>
							<input id="chunk-size" type="number" bind:value={searchChunkSize} min="100" step="50"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="chunk-overlap">Chunk Overlap (chars)</label>
							<input id="chunk-overlap" type="number" bind:value={searchChunkOverlap} min="0" step="50"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('search', saveSearch)}
				</div>
			</Card>

		<!-- Trust Tuning -->
		{:else if activeSection === 'trust'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Trust Tuning</h2>
					<p class="text-xs text-text-dim mt-0.5">Trust score changes per interaction. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-inc">Increase Per Event</label>
							<input id="trust-inc" type="number" bind:value={trustIncrease}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-dec">Decrease Per Event</label>
							<input id="trust-dec" type="number" bind:value={trustDecrease}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="gain-cap">Session Gain Cap</label>
							<input id="gain-cap" type="number" bind:value={trustSessionGain}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="loss-cap">Session Loss Cap</label>
							<input id="loss-cap" type="number" bind:value={trustSessionLoss}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-min">Min Score</label>
							<input id="trust-min" type="number" bind:value={trustMin}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-max">Max Score</label>
							<input id="trust-max" type="number" bind:value={trustMax}
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('trust', saveTrust)}
				</div>
			</Card>

		<!-- Context Tuning -->
		{:else if activeSection === 'context'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Context Tuning</h2>
					<p class="text-xs text-text-dim mt-0.5">Controls how much context the engine assembles per request. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-3 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="max-docs">Max Documents</label>
							<input id="max-docs" type="number" bind:value={contextMaxDocs} min="1" max="50"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="max-hops">Max Graph Hops</label>
							<input id="max-hops" type="number" bind:value={contextMaxHops} min="1" max="5"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="stale">Stale After (exchanges)</label>
							<input id="stale" type="number" bind:value={contextStaleAfter} min="1"
							class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('context', saveContext)}
				</div>
			</Card>

		<!-- API Keys -->
		{:else if activeSection === 'apikeys'}
			<Card>
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">API Keys</h2>
					<p class="text-xs text-text-dim mt-0.5">Keys are write-only — values are never sent to the browser.</p>
				</div>
				<div class="p-4 space-y-4">
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="or-key">OpenRouter API Key</label>
						<div class="flex gap-2">
							{#if keyVisible}
								<InputField id="or-key" bind:value={openrouterKey}
									placeholder="sk-or-..." class="flex-1 font-mono" />
							{:else}
								<InputField id="or-key" type="password" bind:value={openrouterKey}
									placeholder="Enter new key to update..." class="flex-1 font-mono" />
							{/if}
							<Btn small onclick={() => (keyVisible = !keyVisible)}>
								{keyVisible ? 'Hide' : 'Show'}
							</Btn>
						</div>
						<p class="text-xs text-text-dim mt-1.5">Saved to .env only. Used for all LLM and embedding calls via OpenRouter.</p>
					</div>
					{@render saveButton('apikeys', saveApiKey)}
				</div>
			</Card>
		{/if}
	</div>
</div>

{#snippet infoRow(label: string, value: string)}
	<div class="flex items-baseline justify-between py-1">
		<span class="text-xs font-medium text-text-dim">{label}</span>
		<span class="text-sm text-text font-mono">{value}</span>
	</div>
{/snippet}

{#snippet statCell(label: string, value: string)}
	<div class="bg-bg-subtle rounded-md px-3 py-2">
		<p class="text-xs text-text-dim">{label}</p>
		<p class="text-sm font-medium text-text mt-0.5">{value}</p>
	</div>
{/snippet}

{#snippet saveButton(section: string, onSave: () => void)}
	<div class="flex items-center justify-end gap-3 pt-2 border-t border-border-custom">
		{#if saveStatus[section] === 'saved'}
			<span class="text-xs text-success">Saved</span>
		{:else if saveStatus[section] === 'error'}
			<span class="text-xs text-error">Save failed</span>
		{/if}
		<Btn primary onclick={onSave} disabled={saveStatus[section] === 'saving'}>
			{saveStatus[section] === 'saving' ? 'Saving...' : 'Save'}
		</Btn>
	</div>
{/snippet}
