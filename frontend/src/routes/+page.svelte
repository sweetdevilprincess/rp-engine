<script lang="ts">
	import { goto } from '$app/navigation';
	import { rpList, activeRP, activeBranch } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import { addToast } from '$lib/stores/ui';
	import { createRP, listRPs, getAvatarUrl, importRP } from '$lib/api/rp';
	import StatusBadge from '$lib/components/ui/StatusBadge.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import InputField from '$lib/components/ui/InputField.svelte';
	import Btn from '$lib/components/ui/Btn.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Divider from '$lib/components/ui/Divider.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';
	import SelectField from '$lib/components/ui/SelectField.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import FormField from '$lib/components/ui/FormField.svelte';
	import type { RPCreate, RPResponse, ImportResponse } from '$lib/types';

	let rpName = $state('');
	let povMode: 'single' | 'dual' = $state('single');
	let scenePacing: 'slow' | 'moderate' | 'fast' = $state('moderate');
	let tone = $state('');
	let dualCharacters = $state('');
	let creating = $state(false);
	let createdFiles: string[] = $state([]);
	let importing = $state(false);
	let importResult = $state<ImportResponse | null>(null);
	let fileInput: HTMLInputElement;

	async function handleImport(e: Event) {
		const target = e.target as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;
		importing = true;
		importResult = null;
		try {
			const result = await importRP(file);
			importResult = result;
			addToast(`Imported "${result.rp_folder}" successfully`, 'success');
			const rps = await listRPs();
			rpList.set(rps);
		} catch (err: any) {
			addToast(err.message ?? 'Import failed', 'error');
		} finally {
			importing = false;
			target.value = '';
		}
	}

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

<div class="max-w-[720px] mx-auto space-y-6">
	<PageHeader title="RP Engine">
		{#snippet actions()}<StatusBadge />{/snippet}
	</PageHeader>

	<p class="text-text-dim text-[13px] font-serif italic text-center">Every story needs a world to live in.</p>

	<Divider />

	<!-- RP List -->
	<section class="space-y-4">
		<SectionLabel>Your RPs</SectionLabel>

		{#if $serverHealth.status === 'offline'}
			<EmptyState message="Could not connect to RP Engine API" variant="error" />
		{:else if $rpList.length === 0}
			<EmptyState message="No RPs found. Create one below!" />
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				{#each $rpList as rp}
					<Card hover onclick={() => selectRP(rp)}>
						<div class="p-4 text-left group flex gap-3 items-start">
							{#if rp.has_avatar}
								<img
									src={getAvatarUrl(rp.rp_folder)}
									alt={rp.rp_folder}
									class="w-10 h-10 rounded-full object-cover border border-[var(--color-border-custom)] flex-shrink-0"
								/>
							{/if}
							<div class="flex-1 min-w-0">
								<div class="flex items-start justify-between mb-2">
									<h3 class="font-semibold text-text group-hover:text-accent transition-colors">
										{rp.rp_folder}
									</h3>
									<Badge>{rp.card_count} cards</Badge>
								</div>
								<div class="flex items-center gap-2 flex-wrap">
									{#if rp.has_guidelines}
										<Badge color="var(--color-success)" bg="var(--color-success-soft)">Guidelines</Badge>
									{/if}
									{#each rp.branches as branch}
										<Badge>{branch}</Badge>
									{/each}
								</div>
							</div>
						</div>
					</Card>
				{/each}
			</div>
		{/if}
	</section>

	<Divider />

	<!-- Import RP -->
	<Card>
		<div class="p-6 space-y-3">
			<h2 class="text-lg font-semibold text-text font-serif">Import RP</h2>
			<p class="text-sm text-text-dim">Import an RP from a previously exported ZIP archive.</p>
			<input
				bind:this={fileInput}
				type="file"
				accept=".zip"
				onchange={handleImport}
				class="hidden"
			/>
			<Btn onclick={() => fileInput.click()} disabled={importing}>
				{importing ? 'Importing...' : 'Choose ZIP File'}
			</Btn>
			{#if importResult}
				<div class="bg-bg-subtle rounded-md p-3 space-y-1">
					<p class="text-sm font-medium text-success">Imported: {importResult.rp_folder}</p>
					<div class="text-xs text-text-dim space-y-0.5">
						<p>{importResult.stats.exchanges_imported} exchanges, {importResult.stats.sessions_imported} sessions</p>
						<p>{importResult.stats.cards_written} cards, {importResult.stats.branches_imported} branches</p>
						{#if importResult.stats.bookmarks_imported > 0}
							<p>{importResult.stats.bookmarks_imported} bookmarks, {importResult.stats.annotations_imported} annotations</p>
						{/if}
						{#if importResult.stats.warnings.length > 0}
							<div class="mt-2">
								<p class="text-warning font-medium">Warnings:</p>
								{#each importResult.stats.warnings as warning}
									<p class="text-warning">{warning}</p>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</Card>

	<Divider />

	<!-- Create RP Form -->
	<Card>
		<div class="p-6 space-y-4">
		<h2 class="text-lg font-semibold text-text font-serif">Create New RP</h2>

		<div class="space-y-4">
			<FormField label="RP Name" id="rp-name">
				<InputField id="rp-name" bind:value={rpName} placeholder="e.g. My Fantasy RP" />
			</FormField>

			<div class="grid grid-cols-2 gap-4">
				<FormField label="POV Mode" id="pov-mode">
					<SelectField id="pov-mode" bind:value={povMode}
						options={[{value: 'single', label: 'Single'}, {value: 'dual', label: 'Dual'}]} />
				</FormField>
				<FormField label="Scene Pacing" id="scene-pacing">
					<SelectField id="scene-pacing" bind:value={scenePacing}
						options={[{value: 'slow', label: 'Slow'}, {value: 'moderate', label: 'Moderate'}, {value: 'fast', label: 'Fast'}]} />
				</FormField>
			</div>

			<FormField label="Tone" id="tone">
				<InputField id="tone" bind:value={tone} placeholder="e.g. dark, gritty, romantic" />
			</FormField>

			{#if povMode === 'dual'}
				<FormField label="Dual Characters" id="dual-chars">
					<InputField id="dual-chars" bind:value={dualCharacters} placeholder="Character1, Character2" />
				</FormField>
			{/if}

			<Btn primary onclick={handleCreate} disabled={creating || !rpName.trim()}>
				{creating ? 'Creating...' : 'Create RP'}
			</Btn>
		</div>

		{#if createdFiles.length > 0}
			<div class="bg-bg-subtle rounded-md p-3">
				<p class="text-xs text-text-dim mb-1">Created files:</p>
				<pre class="text-xs text-success font-mono">{createdFiles.join('\n')}</pre>
			</div>
		{/if}
	</div>
	</Card>
</div>
