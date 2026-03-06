<script lang="ts">
	import { getSceneContext } from '$lib/api/context';
	import { addToast } from '$lib/stores/ui';
	import type { ContextResponse } from '$lib/types';

	let message = '';
	let lastResponse = '';
	let showLastResponse = false;
	let loading = false;
	let result: ContextResponse | null = null;

	async function inspect() {
		if (!message.trim()) return;
		loading = true;
		result = null;
		try {
			result = await getSceneContext(message.trim(), lastResponse.trim() || undefined);
		} catch (err: any) {
			addToast(err.message ?? 'Inspection failed', 'error');
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) inspect();
	}

	// Source badge styles
	const sourceBadge: Record<string, string> = {
		keyword:     'bg-accent/15 text-accent',
		semantic:    'bg-warm/15 text-warm',
		graph:       'bg-success/15 text-success',
		trigger:     'bg-gold/15 text-gold',
		always_load: 'bg-bg-subtle text-text-dim',
	};

	const alertBadge: Record<string, string> = {
		gentle:   'bg-gold/15 text-gold',
		moderate: 'bg-warm/15 text-warm',
		strong:   'bg-error/15 text-error',
	};

	const injectBadge: Record<string, string> = {
		context_note: 'bg-accent/15 text-accent',
		state_alert:  'bg-gold/15 text-gold',
	};

	// Determine default open state for a section based on data presence
	function defaultOpen(count: number, important: boolean): boolean {
		return important ? count > 0 : false;
	}
</script>

<div class="space-y-2">
	<!-- Query input -->
	<div class="bg-surface rounded border border-border-custom p-3 space-y-2">
		<div class="flex items-center justify-between">
			<h2 class="text-xs font-semibold text-text">Context Inspector</h2>
			<span class="text-xs text-text-dim">Ctrl+Enter to inspect</span>
		</div>

		<textarea
			bind:value={message}
			onkeydown={handleKeydown}
			placeholder="Enter a user message to inspect what context the engine would return..."
			rows="3"
			class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
				placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
		></textarea>

		<div class="flex items-center gap-3">
			<button
				class="text-xs text-text-dim hover:text-text transition-colors"
				onclick={() => (showLastResponse = !showLastResponse)}
			>
				{showLastResponse ? '▾' : '▸'} Last response (optional)
			</button>
		</div>

		{#if showLastResponse}
			<textarea
				bind:value={lastResponse}
				placeholder="Paste the previous assistant response for better context..."
				rows="2"
				class="w-full bg-bg-subtle border border-border-custom rounded-md px-3 py-2 text-sm text-text
					placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
			></textarea>
		{/if}

		<button
			class="w-full bg-accent hover:bg-accent-hover text-white text-sm font-medium py-2 px-4 rounded-md
				transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
			onclick={inspect}
			disabled={loading || !message.trim()}
		>
			{loading ? 'Inspecting...' : 'Inspect'}
		</button>
	</div>

	<!-- Results -->
	{#if result}
		<!-- Stats bar -->
		<div class="bg-surface rounded border border-border-custom px-3 py-1.5 flex flex-wrap gap-3 text-xs text-text-dim">
			<span>Exchange <span class="text-text font-medium">#{result.current_exchange}</span></span>
			<span>Cards pulled <span class="text-text font-medium">{result.documents.length}</span></span>
			<span>NPCs <span class="text-text font-medium">{result.npc_briefs.length}</span></span>
			{#if result.card_gaps.length > 0}
				<span class="text-warning font-medium">⚠ {result.card_gaps.length} card gap{result.card_gaps.length !== 1 ? 's' : ''}</span>
			{/if}
			{#if result.warnings.length > 0}
				<span class="text-error font-medium">✕ {result.warnings.length} warning{result.warnings.length !== 1 ? 's' : ''}</span>
			{/if}
			{#if result.thread_alerts.length > 0}
				<span class="text-warning font-medium">● {result.thread_alerts.length} thread alert{result.thread_alerts.length !== 1 ? 's' : ''}</span>
			{/if}
		</div>

		<!-- Cards pulled -->
		<details open={defaultOpen(result.documents.length, true)} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Cards Pulled</span>
				<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{result.documents.length}</span>
			</summary>
			{#if result.documents.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.documents as doc}
						<details class="group">
							<summary class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
								<span class="text-xs text-text-dim bg-bg-subtle px-1.5 py-0.5 rounded font-mono">{doc.card_type}</span>
								<span class="text-sm text-text flex-1 min-w-0 truncate">{doc.name}</span>
								<span class="text-xs px-1.5 py-0.5 rounded {sourceBadge[doc.source] ?? 'bg-bg-subtle text-text-dim'} shrink-0">
									{doc.source}
								</span>
								<span class="text-xs text-text-dim shrink-0">{doc.relevance_score.toFixed(3)}</span>
								{#if doc.status === 'new'}
									<span class="text-xs bg-success/20 text-success px-1.5 py-0.5 rounded shrink-0">new</span>
								{/if}
							</summary>
							{#if doc.summary || doc.content}
								<div class="px-3 pb-2 pt-1 text-xs text-text-dim border-t border-border-custom bg-bg-subtle/50">
									<p class="whitespace-pre-wrap">{doc.summary ?? doc.content}</p>
								</div>
							{/if}
						</details>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">No cards pulled</p>
			{/if}
		</details>

		<!-- NPC Briefs -->
		<details open={defaultOpen(result.npc_briefs.length, true)} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">NPC Briefs</span>
				<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{result.npc_briefs.length}</span>
			</summary>
			{#if result.npc_briefs.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.npc_briefs as npc}
						<details>
							<summary class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
								<span class="text-sm font-medium text-text">{npc.character}</span>
								{#if npc.archetype}
									<span class="text-xs text-text-dim">{npc.archetype}</span>
								{/if}
								<span class="flex-1"></span>
								{#if npc.trust_stage}
									<span class="text-xs bg-accent/20 text-accent px-1.5 py-0.5 rounded shrink-0">{npc.trust_stage}</span>
								{/if}
								<span class="text-xs text-text-dim shrink-0">{npc.trust_score}</span>
								{#if npc.emotional_state}
									<span class="text-xs text-text-dim shrink-0 italic">{npc.emotional_state}</span>
								{/if}
							</summary>
							<div class="px-3 pb-2 pt-1 space-y-2 border-t border-border-custom bg-bg-subtle/50">
								{#if npc.behavioral_direction}
									<p class="text-xs text-text">{npc.behavioral_direction}</p>
								{/if}
								{#if npc.conditions.length > 0}
									<div class="flex flex-wrap gap-1">
										<span class="text-xs text-text-dim">Conditions:</span>
										{#each npc.conditions as c}
											<span class="text-xs bg-warning/20 text-warning px-1.5 py-0.5 rounded">{c}</span>
										{/each}
									</div>
								{/if}
								{#if npc.scene_signals.length > 0}
									<div class="flex flex-wrap gap-1">
										<span class="text-xs text-text-dim">Signals:</span>
										{#each npc.scene_signals as s}
											<span class="text-xs bg-bg-subtle text-text-dim px-1.5 py-0.5 rounded">{s}</span>
										{/each}
									</div>
								{/if}
								{#if npc.behavioral_modifiers.length > 0}
									<div class="flex flex-wrap gap-1">
										<span class="text-xs text-text-dim">Modifiers:</span>
										{#each npc.behavioral_modifiers as m}
											<span class="text-xs bg-bg-subtle text-text-dim px-1.5 py-0.5 rounded">{m}</span>
										{/each}
									</div>
								{/if}
							</div>
						</details>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">No NPC briefs</p>
			{/if}
		</details>

		<!-- Thread Alerts -->
		<details open={defaultOpen(result.thread_alerts.length, true)} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Thread Alerts</span>
				<span class="text-xs {result.thread_alerts.length > 0 ? 'bg-warning/20 text-warning' : 'bg-bg-subtle text-text-dim'} px-2 py-0.5 rounded-full">
					{result.thread_alerts.length}
				</span>
			</summary>
			{#if result.thread_alerts.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.thread_alerts as alert}
						<div class="px-3 py-1.5 space-y-1">
							<div class="flex items-center gap-2">
								<span class="text-sm text-text">{alert.name}</span>
								<span class="text-xs px-1.5 py-0.5 rounded {alertBadge[alert.level] ?? 'bg-bg-subtle text-text-dim'}">{alert.level}</span>
								<span class="text-xs text-text-dim ml-auto">{alert.counter} / {alert.threshold}</span>
							</div>
							<p class="text-xs text-text-dim">{alert.consequence}</p>
						</div>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">No thread alerts</p>
			{/if}
		</details>

		<!-- Triggered Notes -->
		<details open={defaultOpen(result.triggered_notes.length, true)} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Triggered Notes</span>
				<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{result.triggered_notes.length}</span>
			</summary>
			{#if result.triggered_notes.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.triggered_notes as note}
						<details>
							<summary class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
								<span class="text-sm text-text">{note.trigger_name}</span>
								<span class="text-xs px-1.5 py-0.5 rounded {injectBadge[note.inject_type] ?? 'bg-bg-subtle text-text-dim'}">{note.inject_type}</span>
								{#if note.signals_matched.length > 0}
									<span class="text-xs text-text-dim ml-auto">{note.signals_matched.join(', ')}</span>
								{/if}
							</summary>
							<div class="px-3 pb-2 pt-1 border-t border-border-custom bg-bg-subtle/50">
								<p class="text-xs text-text whitespace-pre-wrap">{note.content}</p>
							</div>
						</details>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">No triggered notes</p>
			{/if}
		</details>

		<!-- Card Gaps -->
		<details open={defaultOpen(result.card_gaps.length, true)} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Card Gaps</span>
				<span class="text-xs {result.card_gaps.length > 0 ? 'bg-warning/20 text-warning' : 'bg-bg-subtle text-text-dim'} px-2 py-0.5 rounded-full">
					{result.card_gaps.length}
				</span>
			</summary>
			{#if result.card_gaps.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.card_gaps as gap}
						<div class="flex items-center gap-2 px-3 py-1.5">
							<span class="text-sm text-text">{gap.entity_name}</span>
							{#if gap.suggested_type}
								<span class="text-xs bg-bg-subtle text-text-dim px-1.5 py-0.5 rounded">{gap.suggested_type}</span>
							{/if}
							<span class="text-xs text-text-dim ml-auto">seen {gap.seen_count}×</span>
						</div>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">No card gaps</p>
			{/if}
		</details>

		<!-- Scene State -->
		<details open={false} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Scene State</span>
			</summary>
			<div class="border-t border-border-custom px-3 py-2 grid grid-cols-2 gap-1.5 text-xs">
				<div><span class="text-text-dim">Location:</span> <span class="text-text">{result.scene_state.location ?? '—'}</span></div>
				<div><span class="text-text-dim">Time:</span> <span class="text-text">{result.scene_state.time_of_day ?? '—'}</span></div>
				<div><span class="text-text-dim">Mood:</span> <span class="text-text">{result.scene_state.mood ?? '—'}</span></div>
				<div><span class="text-text-dim">Timestamp:</span> <span class="text-text">{result.scene_state.in_story_timestamp ?? '—'}</span></div>
			</div>
		</details>

		<!-- Character States -->
		{#if Object.keys(result.character_states).length > 0}
			<details open={false} class="bg-surface rounded border border-border-custom overflow-hidden">
				<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
					<span class="text-sm font-medium text-text">Character States</span>
					<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{Object.keys(result.character_states).length}</span>
				</summary>
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each Object.entries(result.character_states) as [name, state]}
						<div class="px-3 py-1.5 text-xs space-y-1">
							<span class="text-sm font-medium text-text">{name}</span>
							<div class="grid grid-cols-2 gap-1 mt-1">
								<div><span class="text-text-dim">Location:</span> <span class="text-text">{state.location ?? '—'}</span></div>
								<div><span class="text-text-dim">Emotional:</span> <span class="text-text">{state.emotional_state ?? '—'}</span></div>
								{#if state.conditions.length > 0}
									<div class="col-span-2 flex flex-wrap gap-1 mt-0.5">
										{#each state.conditions as c}
											<span class="bg-warning/20 text-warning px-1.5 py-0.5 rounded">{c}</span>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</details>
		{/if}

		<!-- Already-loaded References -->
		<details open={false} class="bg-surface rounded border border-border-custom overflow-hidden">
			<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
				<span class="text-sm font-medium text-text">Already Loaded</span>
				<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{result.references.length}</span>
			</summary>
			{#if result.references.length > 0}
				<div class="border-t border-border-custom divide-y divide-border-custom">
					{#each result.references as ref}
						<div class="flex items-center gap-2 px-3 py-1.5 text-xs">
							<span class="text-text-dim bg-bg-subtle px-1.5 py-0.5 rounded">{ref.card_type}</span>
							<span class="text-text">{ref.name}</span>
							<span class="text-text-dim ml-auto">turn {ref.sent_at_turn}</span>
						</div>
					{/each}
				</div>
			{:else}
				<p class="px-3 py-2 text-xs text-text-dim border-t border-border-custom">None</p>
			{/if}
		</details>

		<!-- Warnings -->
		{#if result.warnings.length > 0}
			<details open={true} class="bg-surface rounded-lg border border-error/30 overflow-hidden">
				<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
					<span class="text-sm font-medium text-error">Warnings</span>
					<span class="text-xs bg-error/20 text-error px-2 py-0.5 rounded-full">{result.warnings.length}</span>
				</summary>
				<div class="border-t border-error/20 divide-y divide-border-custom">
					{#each result.warnings as w}
						<div class="px-3 py-1.5 text-xs space-y-0.5">
							<div class="text-error">{w.type}</div>
							<div class="text-text-dim">Exchange {w.exchange} · Failed at {w.failed_at}</div>
							{#if w.stale_fields.length > 0}
								<div class="text-text-dim">Stale: {w.stale_fields.join(', ')}</div>
							{/if}
						</div>
					{/each}
				</div>
			</details>
		{/if}

		<!-- Writing Constraints -->
		{#if result.writing_constraints}
			<details open={false} class="bg-surface rounded border border-border-custom overflow-hidden">
				<summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-subtle transition-colors list-none">
					<span class="text-sm font-medium text-text">Writing Constraints</span>
					<span class="text-xs bg-bg-subtle text-text-dim px-2 py-0.5 rounded-full">{result.writing_constraints.token_count} tokens</span>
				</summary>
				<div class="border-t border-border-custom px-3 py-2 space-y-1.5 text-xs">
					<p class="text-text whitespace-pre-wrap">{result.writing_constraints.text}</p>
					{#if result.writing_constraints.patterns_included.length > 0}
						<div class="flex flex-wrap gap-1 pt-1">
							{#each result.writing_constraints.patterns_included as p}
								<span class="bg-bg-subtle text-text-dim px-1.5 py-0.5 rounded">{p}</span>
							{/each}
						</div>
					{/if}
				</div>
			</details>
		{/if}
	{/if}
</div>
