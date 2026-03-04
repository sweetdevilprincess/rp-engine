<script lang="ts">
	import { onMount } from 'svelte';
	import { getConfig, updateConfig } from '$lib/api/config';

	const sections = [
		{ id: 'server',   label: 'Server'         },
		{ id: 'llm',      label: 'LLM Models'     },
		{ id: 'search',   label: 'Search Tuning'  },
		{ id: 'trust',    label: 'Trust Tuning'   },
		{ id: 'context',  label: 'Context Tuning' },
		{ id: 'apikeys',  label: 'API Keys'       },
	];

	let activeSection = 'server';
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

	// API Keys
	let openrouterKey = '';
	let keyVisible = false;

	onMount(async () => {
		try {
			const cfg = await getConfig();
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

<div class="flex gap-4">
	<!-- Left section navigator -->
	<nav class="w-44 shrink-0 bg-surface rounded-lg border border-border-custom overflow-hidden self-start">
		<div class="px-3 py-2.5 border-b border-border-custom">
			<span class="text-xs font-semibold text-text-dim uppercase tracking-wider">Settings</span>
		</div>
		<div class="p-1.5 space-y-0.5">
			{#each sections as section}
				<button
					class="w-full flex items-center px-3 py-2 rounded-md text-sm text-left transition-colors
						{activeSection === section.id
							? 'bg-accent/20 text-accent'
							: 'text-text-dim hover:text-text hover:bg-surface2'}"
					on:click={() => (activeSection = section.id)}
				>
					{section.label}
				</button>
			{/each}
		</div>
	</nav>

	<!-- Section content -->
	<div class="flex-1 min-w-0 max-w-2xl">

		{#if loadError}
			<div class="bg-error/10 border border-error/30 rounded-lg px-4 py-2.5 text-sm text-error mb-4">
				Failed to load config: {loadError}
			</div>
		{/if}

		<!-- Server -->
		{#if activeSection === 'server'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Server</h2>
					<p class="text-xs text-text-dim mt-0.5">Changes to host or port require a server restart.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="host">Host</label>
							<input id="host" type="text" bind:value={serverHost}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="port">Port</label>
							<input id="port" type="number" bind:value={serverPort} min="1024" max="65535"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('server', saveServer)}
				</div>
			</div>

		<!-- LLM Models -->
		{:else if activeSection === 'llm'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">LLM Models</h2>
					<p class="text-xs text-text-dim mt-0.5">Model IDs passed to OpenRouter. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-npc">NPC Reactions</label>
						<input id="llm-npc" type="text" bind:value={llmNpcReactions}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-analysis">Response Analysis</label>
						<input id="llm-analysis" type="text" bind:value={llmAnalysis}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-cardgen">Card Generation</label>
						<input id="llm-cardgen" type="text" bind:value={llmCardGen}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-embed">Embeddings</label>
						<input id="llm-embed" type="text" bind:value={llmEmbeddings}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-fallback">Fallback Model</label>
						<input id="llm-fallback" type="text" bind:value={llmFallback}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="llm-pov">Default POV Character</label>
						<input id="llm-pov" type="text" bind:value={llmDefaultPov}
							class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
								focus:outline-none focus:ring-1 focus:ring-accent" />
					</div>
					{@render saveButton('llm', saveLlm)}
				</div>
			</div>

		<!-- Search Tuning -->
		{:else if activeSection === 'search'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
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
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="bm25-weight">BM25 Weight</label>
							<input id="bm25-weight" type="number" bind:value={searchBm25Weight}
								min="0" max="1" step="0.05"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="threshold">Similarity Threshold</label>
							<input id="threshold" type="number" bind:value={searchThreshold}
								min="0" max="1" step="0.05"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="chunk-size">Chunk Size (chars)</label>
							<input id="chunk-size" type="number" bind:value={searchChunkSize} min="100" step="50"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="chunk-overlap">Chunk Overlap (chars)</label>
							<input id="chunk-overlap" type="number" bind:value={searchChunkOverlap} min="0" step="50"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('search', saveSearch)}
				</div>
			</div>

		<!-- Trust Tuning -->
		{:else if activeSection === 'trust'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Trust Tuning</h2>
					<p class="text-xs text-text-dim mt-0.5">Trust score changes per interaction. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-inc">Increase Per Event</label>
							<input id="trust-inc" type="number" bind:value={trustIncrease}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-dec">Decrease Per Event</label>
							<input id="trust-dec" type="number" bind:value={trustDecrease}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="gain-cap">Session Gain Cap</label>
							<input id="gain-cap" type="number" bind:value={trustSessionGain}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="loss-cap">Session Loss Cap</label>
							<input id="loss-cap" type="number" bind:value={trustSessionLoss}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-min">Min Score</label>
							<input id="trust-min" type="number" bind:value={trustMin}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="trust-max">Max Score</label>
							<input id="trust-max" type="number" bind:value={trustMax}
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('trust', saveTrust)}
				</div>
			</div>

		<!-- Context Tuning -->
		{:else if activeSection === 'context'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">Context Tuning</h2>
					<p class="text-xs text-text-dim mt-0.5">Controls how much context the engine assembles per request. Requires server restart to take effect.</p>
				</div>
				<div class="p-4 space-y-4">
					<div class="grid grid-cols-3 gap-4">
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="max-docs">Max Documents</label>
							<input id="max-docs" type="number" bind:value={contextMaxDocs} min="1" max="50"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="max-hops">Max Graph Hops</label>
							<input id="max-hops" type="number" bind:value={contextMaxHops} min="1" max="5"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
						<div>
							<label class="block text-xs font-medium text-text-dim mb-1" for="stale">Stale After (exchanges)</label>
							<input id="stale" type="number" bind:value={contextStaleAfter} min="1"
								class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text
									focus:outline-none focus:ring-1 focus:ring-accent" />
						</div>
					</div>
					{@render saveButton('context', saveContext)}
				</div>
			</div>

		<!-- API Keys -->
		{:else if activeSection === 'apikeys'}
			<div class="bg-surface rounded-lg border border-border-custom overflow-hidden">
				<div class="px-4 py-3 border-b border-border-custom">
					<h2 class="text-sm font-semibold text-text">API Keys</h2>
					<p class="text-xs text-text-dim mt-0.5">Keys are write-only — values are never sent to the browser.</p>
				</div>
				<div class="p-4 space-y-4">
					<div>
						<label class="block text-xs font-medium text-text-dim mb-1" for="or-key">OpenRouter API Key</label>
						<div class="flex gap-2">
							{#if keyVisible}
								<input id="or-key" type="text" bind:value={openrouterKey}
									placeholder="sk-or-..."
									class="flex-1 bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
										focus:outline-none focus:ring-1 focus:ring-accent" />
							{:else}
								<input id="or-key" type="password" bind:value={openrouterKey}
									placeholder="Enter new key to update..."
									class="flex-1 bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text font-mono
										focus:outline-none focus:ring-1 focus:ring-accent" />
							{/if}
							<button
								class="px-3 py-2 bg-surface2 border border-border-custom rounded-md text-xs text-text-dim
									hover:text-text hover:bg-surface transition-colors"
								on:click={() => (keyVisible = !keyVisible)}
							>
								{keyVisible ? 'Hide' : 'Show'}
							</button>
						</div>
						<p class="text-xs text-text-dim mt-1.5">Saved to .env only. Used for all LLM and embedding calls via OpenRouter.</p>
					</div>
					{@render saveButton('apikeys', saveApiKey)}
				</div>
			</div>
		{/if}
	</div>
</div>

{#snippet saveButton(section: string, onSave: () => void)}
	<div class="flex items-center justify-end gap-3 pt-2 border-t border-border-custom">
		{#if saveStatus[section] === 'saved'}
			<span class="text-xs text-success">Saved</span>
		{:else if saveStatus[section] === 'error'}
			<span class="text-xs text-error">Save failed</span>
		{/if}
		<button
			on:click={onSave}
			disabled={saveStatus[section] === 'saving'}
			class="bg-accent text-white text-sm font-medium py-1.5 px-4 rounded-md
				hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
		>
			{saveStatus[section] === 'saving' ? 'Saving...' : 'Save'}
		</button>
	</div>
{/snippet}
