<script lang="ts">
	import { goto } from '$app/navigation';
	import { rpList, activeRP, activeBranch } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import { addToast } from '$lib/stores/ui';
	import { createRP, listRPs } from '$lib/api/rp';
	import StatusBadge from '$lib/components/ui/StatusBadge.svelte';
	import type { RPCreate, RPResponse } from '$lib/types';

	let rpName = '';
	let povMode: 'single' | 'dual' = 'single';
	let scenePacing: 'slow' | 'moderate' | 'fast' = 'moderate';
	let tone = '';
	let dualCharacters = '';
	let creating = false;
	let createdFiles: string[] = [];

	async function handleCreate() {
		if (!rpName.trim()) return;
		creating = true;
		createdFiles = [];
		try {
			const body: RPCreate = {
				rp_name: rpName.trim(),
				pov_mode: povMode,
				scene_pacing: scenePacing,
			};
			if (tone.trim()) body.tone = tone.trim();
			if (povMode === 'dual' && dualCharacters.trim()) {
				body.dual_characters = dualCharacters.split(',').map((s) => s.trim()).filter(Boolean);
			}
			const result: RPResponse = await createRP(body);
			createdFiles = result.created_files;
			addToast(`Created RP "${result.rp_folder}"`, 'success');
			rpName = '';
			tone = '';
			dualCharacters = '';
			const rps = await listRPs();
			rpList.set(rps);
		} catch (err: any) {
			addToast(err.message ?? 'Failed to create RP', 'error');
		} finally {
			creating = false;
		}
	}

	function selectRP(rp: typeof $rpList[0]) {
		activeRP.set(rp);
		activeBranch.set('main');
		goto(`/${rp.rp_folder}/`);
	}
</script>

<div class="max-w-4xl mx-auto space-y-8">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold text-text">RP Engine</h1>
		<StatusBadge />
	</div>

	<!-- RP List -->
	<section class="space-y-4">
		<h2 class="text-lg font-semibold text-text">Your RPs</h2>

		{#if $serverHealth.status === 'offline'}
			<div class="bg-error/10 border border-error/30 rounded-lg p-4 text-error text-sm">
				Could not connect to RP Engine API
			</div>
		{:else if $rpList.length === 0}
			<div class="bg-surface border border-border-custom rounded-lg p-8 text-center text-text-dim">
				No RPs found. Create one below!
			</div>
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				{#each $rpList as rp}
					<button
						class="bg-surface border border-border-custom rounded-lg p-4 text-left hover:border-accent/50 transition-colors group"
						on:click={() => selectRP(rp)}
					>
						<div class="flex items-start justify-between mb-2">
							<h3 class="font-semibold text-text group-hover:text-accent transition-colors">
								{rp.rp_folder}
							</h3>
							<span class="text-xs text-text-dim bg-surface2 px-2 py-0.5 rounded-full">
								{rp.card_count} cards
							</span>
						</div>
						<div class="flex items-center gap-2 flex-wrap">
							{#if rp.has_guidelines}
								<span class="text-xs text-success bg-success/10 px-2 py-0.5 rounded-full">
									Guidelines
								</span>
							{/if}
							{#each rp.branches as branch}
								<span class="text-xs text-text-dim bg-surface2 px-2 py-0.5 rounded-full">
									{branch}
								</span>
							{/each}
						</div>
					</button>
				{/each}
			</div>
		{/if}
	</section>

	<!-- Create RP Form -->
	<section class="bg-surface border border-border-custom rounded-lg p-6 space-y-4">
		<h2 class="text-lg font-semibold text-text">Create New RP</h2>

		<div class="space-y-4">
			<div>
				<label class="block text-sm font-medium text-text-dim mb-1" for="rp-name">RP Name</label>
				<input
					id="rp-name"
					type="text"
					bind:value={rpName}
					placeholder="e.g. My Fantasy RP"
					class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
				/>
			</div>

			<div class="grid grid-cols-2 gap-4">
				<div>
					<label class="block text-sm font-medium text-text-dim mb-1" for="pov-mode">POV Mode</label>
					<select
						id="pov-mode"
						bind:value={povMode}
						class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
					>
						<option value="single">Single</option>
						<option value="dual">Dual</option>
					</select>
				</div>
				<div>
					<label class="block text-sm font-medium text-text-dim mb-1" for="scene-pacing">Scene Pacing</label>
					<select
						id="scene-pacing"
						bind:value={scenePacing}
						class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-accent"
					>
						<option value="slow">Slow</option>
						<option value="moderate">Moderate</option>
						<option value="fast">Fast</option>
					</select>
				</div>
			</div>

			<div>
				<label class="block text-sm font-medium text-text-dim mb-1" for="tone">Tone</label>
				<input
					id="tone"
					type="text"
					bind:value={tone}
					placeholder="e.g. dark, gritty, romantic"
					class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
				/>
			</div>

			{#if povMode === 'dual'}
				<div>
					<label class="block text-sm font-medium text-text-dim mb-1" for="dual-chars">Dual Characters</label>
					<input
						id="dual-chars"
						type="text"
						bind:value={dualCharacters}
						placeholder="Character1, Character2"
						class="w-full bg-surface2 border border-border-custom rounded-md px-3 py-2 text-sm text-text placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent"
					/>
				</div>
			{/if}

			<button
				class="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2 px-4 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				on:click={handleCreate}
				disabled={creating || !rpName.trim()}
			>
				{creating ? 'Creating...' : 'Create RP'}
			</button>
		</div>

		{#if createdFiles.length > 0}
			<div class="bg-surface2 rounded-md p-3">
				<p class="text-xs text-text-dim mb-1">Created files:</p>
				<pre class="text-xs text-success font-mono">{createdFiles.join('\n')}</pre>
			</div>
		{/if}
	</section>
</div>
