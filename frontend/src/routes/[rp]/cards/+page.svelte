<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { listCards, getCard, createCard, updateCard } from '$lib/api/cards';
	import { getFullState } from '$lib/api/state';
	import { addToast } from '$lib/stores/ui';
	import { activeRP } from '$lib/stores/rp';
	import { CARD_TYPES } from '$lib/types/enums';
	import type { CardType } from '$lib/types/enums';
	import type { StoryCardSummary, StoryCardDetail, StoryCardCreate, StoryCardUpdate } from '$lib/types/cards';
	import type { RelationshipDetail } from '$lib/types/state';
	import { cardTypeColors, importanceColors, trustStageColors } from '$lib/utils/colors';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Btn from '$lib/components/ui/Btn.svelte';
	import InputField from '$lib/components/ui/InputField.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';
	import SideNav from '$lib/components/ui/SideNav.svelte';
	import SelectField from '$lib/components/ui/SelectField.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Divider from '$lib/components/ui/Divider.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import ListItem from '$lib/components/ui/ListItem.svelte';
	import FormField from '$lib/components/ui/FormField.svelte';
	import EntityChip from '$lib/components/ui/EntityChip.svelte';

	// ── Card list state ──
	let cards = $state<StoryCardSummary[]>([]);
	let search = $state('');
	let selectedCard = $state<StoryCardDetail | null>(null);
	let loadingCard = $state(false);
	let loadingList = $state(true);

	// ── Editor state ──
	type EditorMode = 'view' | 'edit' | 'create';
	let mode = $state<EditorMode>('view');

	// ── Form fields ──
	let editYaml = $state('');
	let editContent = $state('');
	let saving = $state(false);

	// ── Create mode ──
	let createType = $state<CardType>('npc');
	let createName = $state('');
	let createStep = $state<1 | 2>(1);

	// ── Relationships from state ──
	let relationships = $state<RelationshipDetail[]>([]);

	// Get relationships for the selected card
	let cardRelationships = $derived.by(() => {
		if (!selectedCard) return [];
		const name = selectedCard.name;
		return relationships.filter(r => r.character_a === name || r.character_b === name);
	});

	// ── Derived ──
	let filteredCards = $derived.by(() => {
		return cards.filter(c => {
			if (!search.trim()) return true;
			const q = search.toLowerCase();
			return c.name.toLowerCase().includes(q) || (c.summary ?? '').toLowerCase().includes(q);
		});
	});

	// ── Init ──
	onMount(async () => {
		await Promise.all([loadCards(), loadRelationships()]);
	});

	async function loadRelationships() {
		try {
			const state = await getFullState();
			relationships = state.relationships;
		} catch {
			// State may not be available yet — relationships just won't show
		}
	}

	async function loadCards() {
		loadingList = true;
		try {
			const res = await listCards();
			cards = res.cards;
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load cards', 'error');
		} finally {
			loadingList = false;
		}
	}

	async function selectCard(card: StoryCardSummary) {
		loadingCard = true;
		mode = 'view';
		try {
			selectedCard = await getCard(card.card_type, card.name);
		} catch (e: any) {
			addToast(e.message ?? 'Failed to load card', 'error');
		} finally {
			loadingCard = false;
		}
	}

	function selectCardByName(name: string) {
		const match = cards.find(c => c.name === name);
		if (match) selectCard(match);
	}

	// ── Editor actions ──
	function enterEditMode() {
		if (!selectedCard) return;
		mode = 'edit';
		editYaml = buildYaml(selectedCard.frontmatter);
		editContent = selectedCard.content;
	}

	function enterCreateMode() {
		mode = 'create';
		createStep = 1;
		createType = 'npc';
		createName = '';
		editYaml = '';
		editContent = '';
		selectedCard = null;
	}

	function startCreateEditor() {
		if (!createName.trim()) {
			addToast('Please enter a card name', 'warning');
			return;
		}
		createStep = 2;
		editYaml = `name: ${createName}`;
		editContent = '';
	}

	function cancelEdit() {
		mode = 'view';
		if (!selectedCard) selectedCard = null;
	}

	async function handleSave() {
		saving = true;
		try {
			const fm = parseYaml(editYaml);
			const content = editContent;

			delete fm['type'];
			delete fm['card_id'];

			if (mode === 'create') {
				const body: StoryCardCreate = { name: createName, frontmatter: fm, content };
				const created = await createCard(createType, body);
				addToast(`Created card: ${created.name}`, 'success');
				await loadCards();
				selectedCard = created;
				mode = 'view';
			} else if (mode === 'edit' && selectedCard) {
				delete fm['name'];
				const body: StoryCardUpdate = { frontmatter: fm, content };
				const updated = await updateCard(selectedCard.card_type, selectedCard.name, body);
				addToast(`Saved card: ${updated.name}`, 'success');
				await loadCards();
				selectedCard = updated;
				mode = 'view';
			}
		} catch (e: any) {
			addToast(e.message ?? 'Save failed', 'error');
		} finally {
			saving = false;
		}
	}

	// ── YAML helpers ──
	function buildYaml(fm: Record<string, unknown>): string {
		const lines: string[] = [];
		for (const [key, val] of Object.entries(fm)) {
			if (val === null || val === undefined) continue;
			if (Array.isArray(val)) {
				if (val.length === 0) {
					lines.push(`${key}: []`);
				} else {
					lines.push(`${key}:`);
					for (const item of val) lines.push(`  - ${item}`);
				}
			} else if (typeof val === 'object') {
				lines.push(`${key}: ${JSON.stringify(val)}`);
			} else {
				lines.push(`${key}: ${val}`);
			}
		}
		return lines.join('\n');
	}

	function parseYaml(yaml: string): Record<string, unknown> {
		const fm: Record<string, unknown> = {};
		let currentKey = '';
		let currentArray: string[] | null = null;

		for (const line of yaml.split('\n')) {
			const trimmed = line.trim();
			if (!trimmed) continue;

			if (trimmed.startsWith('- ') && currentKey) {
				if (!currentArray) currentArray = [];
				currentArray.push(trimmed.slice(2).trim());
				continue;
			}

			if (currentArray && currentKey) {
				fm[currentKey] = currentArray;
				currentArray = null;
			}

			const colonIdx = trimmed.indexOf(':');
			if (colonIdx === -1) continue;

			const key = trimmed.slice(0, colonIdx).trim();
			const val = trimmed.slice(colonIdx + 1).trim();
			currentKey = key;

			if (val === '' || val === '[]') {
				if (val === '[]') fm[key] = [];
				continue;
			}

			if (val.startsWith('{') || val.startsWith('[')) {
				try { fm[key] = JSON.parse(val); continue; } catch {}
			}

			if (val === 'true') { fm[key] = true; continue; }
			if (val === 'false') { fm[key] = false; continue; }
			if (val === 'null') { fm[key] = null; continue; }

			const num = Number(val);
			if (!isNaN(num) && val !== '') { fm[key] = num; continue; }

			fm[key] = val;
		}

		if (currentArray && currentKey) {
			fm[currentKey] = currentArray;
		}

		return fm;
	}
</script>

<!-- 2-column layout -->
<div class="flex gap-3" style="height: calc(100vh - 120px)">

	<!-- ═══ LEFT: Card List ═══ -->
	<SideNav title="Cards" width="w-[260px]">
		<!-- Search -->
		<div class="p-2.5 px-3.5 border-b border-border-custom/60">
			<InputField bind:value={search} placeholder="Search cards..." size="sm" />
		</div>

		<!-- Card list -->
		<div class="flex-1 overflow-y-auto" style="max-height: calc(100vh - 220px)">
			{#if loadingList}
				<div class="p-4 text-xs text-text-dim text-center animate-pulse">Loading cards...</div>
			{:else if filteredCards.length === 0}
				<div class="p-4 text-xs text-text-dim text-center">No cards found.</div>
			{:else}
				{#each filteredCards as card}
					{@const cs = cardTypeColors(card.card_type)}
					<ListItem
						active={selectedCard?.name === card.name && selectedCard?.card_type === card.card_type}
						indicator={cs.hex}
						onclick={() => selectCard(card)}
					>
						<div>
							<div class="text-[13px] font-medium text-text">{card.name}</div>
							<div class="text-[11px] text-text-dim/60">{card.card_type.replace('_', ' ')}</div>
						</div>
					</ListItem>
				{/each}
			{/if}
		</div>

		<!-- New Card button -->
		<div class="p-2 border-t border-border-custom/60">
			<div class="w-full">
				<Btn primary small onclick={enterCreateMode}>+ New Card</Btn>
			</div>
		</div>
	</SideNav>

	<!-- ═══ RIGHT: Card Detail / Editor ═══ -->
	<div class="flex-1 min-w-0">

		{#if mode === 'create' && createStep === 1}
			<!-- Create step 1: pick type + name -->
			<div class="bg-surface border border-border-custom rounded-[10px] p-5 space-y-3">
				<h2 class="text-sm font-medium text-text">New Card</h2>
				<div class="space-y-2">
					<FormField label="Card Type" size="xs">
						<SelectField bind:value={createType}
							options={CARD_TYPES.map(ct => ({value: ct, label: ct.replace('_', ' ')}))} />
					</FormField>
					<FormField label="Name" size="xs">
						<InputField bind:value={createName} placeholder="Card name..." size="sm" onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && startCreateEditor()} />
					</FormField>
				</div>
				<div class="flex gap-2">
					<Btn primary small onclick={startCreateEditor}>Next</Btn>
					<Btn small onclick={cancelEdit}>Cancel</Btn>
				</div>
			</div>

		{:else if mode === 'view' && !selectedCard && !loadingCard}
			<!-- Empty state -->
			<div class="bg-surface border border-border-custom rounded-[10px] flex items-center justify-center" style="min-height: 300px">
				<span class="text-text-dim/60 text-[13px] font-serif italic">Select a card to view details</span>
			</div>

		{:else if loadingCard}
			<div class="bg-surface border border-border-custom rounded-[10px] flex items-center justify-center" style="min-height: 300px">
				<span class="text-xs text-text-dim">Loading card...</span>
			</div>

		{:else if mode === 'view' && selectedCard}
			{@const card = selectedCard}
			<!-- ── VIEW MODE ── -->
			<div class="bg-surface border border-border-custom rounded-[10px]">
				<div class="p-5 px-[22px]">
					<!-- Header -->
					<div class="mb-3">
						<PageHeader title={card.name} size="md">
							{#snippet before()}
								<Badge color={cardTypeColors(card.card_type).text} bg={cardTypeColors(card.card_type).bg}>{card.card_type.replace('_', ' ')}</Badge>
							{/snippet}
							{#snippet badges()}
								{#if card.importance}
									{@const imp = importanceColors(card.importance)}
									<Badge color={imp.text} bg={imp.bg}>{card.importance}</Badge>
								{/if}
							{/snippet}
							{#snippet actions()}
								<Btn small onclick={enterEditMode}>Edit</Btn>
							{/snippet}
						</PageHeader>
					</div>

					<!-- Summary / Content -->
					{#if selectedCard.content}
						<p class="text-[13px] text-text-dim leading-relaxed mb-4">{selectedCard.content}</p>
					{/if}

					<!-- Frontmatter fields -->
					{#if Object.keys(selectedCard.frontmatter).length > 0}
						<div class="mb-4">
							<div class="mb-1"><SectionLabel>Details</SectionLabel></div>
							<div class="space-y-0.5">
								{#each Object.entries(selectedCard.frontmatter) as [key, val]}
									<div class="flex gap-2 text-xs">
										<span class="text-text-dim shrink-0 w-32 truncate">{key}</span>
										<span class="text-text break-all">{typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}</span>
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<Divider />

					<!-- Connections inline -->
					<div class="mt-3">
						<SectionLabel>Connections</SectionLabel>
					</div>

					{#if cardRelationships.length > 0 || selectedCard.connections.length > 0}
						<div class="flex gap-1.5 flex-wrap mt-2">
							<!-- Relationship chips -->
							{#each cardRelationships as rel}
								{@const otherName = rel.character_a === selectedCard.name ? rel.character_b : rel.character_a}
								<EntityChip label="{rel.trust_stage} &rarr;" name={otherName} onclick={() => selectCardByName(otherName)}>
									<span
										class="text-[10px] font-semibold px-1.5 py-px rounded-full ml-0.5
											{rel.live_trust_score >= 75 ? 'text-success bg-success/10' : rel.live_trust_score >= 40 ? 'text-warning bg-warning/10' : 'text-error bg-error/10'}"
									>{rel.live_trust_score}</span>
								</EntityChip>
							{/each}

							<!-- Entity connection chips -->
							{#each selectedCard.connections as conn}
								<EntityChip label="{conn.connection_type} &rarr;" name={conn.to_entity} onclick={() => selectCardByName(conn.to_entity)} />
							{/each}
						</div>
					{:else}
						<p class="text-xs text-text-dim mt-2">No connections</p>
					{/if}
				</div>
			</div>

		{:else if mode === 'edit' || (mode === 'create' && createStep === 2)}
			<!-- ── EDIT MODE ── -->
			<div class="bg-surface border border-border-custom rounded-[10px] flex flex-col" style="max-height: calc(100vh - 120px)">
				<!-- Header with Save/Cancel -->
				<div class="flex justify-between items-center p-5 px-[22px] pb-4">
					<div class="flex items-center gap-2">
						{#if mode === 'edit' && selectedCard}
							<Badge color={cardTypeColors(selectedCard.card_type).text} bg={cardTypeColors(selectedCard.card_type).bg}>{selectedCard.card_type.replace('_', ' ')}</Badge>
							<h2 class="font-serif text-lg font-semibold m-0">{selectedCard.name}</h2>
						{:else}
							<h2 class="text-sm font-medium text-text m-0">Creating {createType.replace('_', ' ')}: {createName}</h2>
						{/if}
					</div>
					<div class="flex gap-1.5">
						<Btn small onclick={cancelEdit}>Cancel</Btn>
						<Btn primary small disabled={saving} onclick={handleSave}>
							{saving ? 'Saving...' : mode === 'create' ? 'Create' : 'Save'}
						</Btn>
					</div>
				</div>

				<div class="flex-1 overflow-y-auto px-[22px] pb-5 space-y-4">
					<!-- Frontmatter (labeled, not collapsible) -->
					<FormField label="Frontmatter" size="xs">
						<textarea
							bind:value={editYaml}
							rows="8"
							class="w-full box-border min-h-[140px] px-3 py-2.5 rounded-lg border border-border-custom bg-surface2 text-xs text-text font-mono leading-relaxed
								focus:outline-none focus:ring-1 focus:ring-accent resize-y"
							spellcheck="false"
						></textarea>
						<p class="text-[11px] text-text-dim/60 mt-1">YAML-style key: value pairs</p>
					</FormField>

					<!-- Content -->
					<FormField label="Content" size="xs">
						<textarea
							bind:value={editContent}
							rows="12"
							class="w-full box-border min-h-[180px] px-3.5 py-2.5 rounded-lg border border-border-custom bg-surface2 text-[13px] text-text leading-relaxed
								focus:outline-none focus:ring-1 focus:ring-accent resize-y"
						></textarea>
					</FormField>
				</div>
			</div>
		{/if}
	</div>
</div>
