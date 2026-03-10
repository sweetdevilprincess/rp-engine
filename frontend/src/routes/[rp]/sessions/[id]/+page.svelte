<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { addToast } from '$lib/stores/ui';
	import { getSessionTimeline } from '$lib/api/sessions';
	import type { SessionTimelineEntry, SessionTimelineResponse } from '$lib/types';
	import { TIMELINE_TYPE_COLORS } from '$lib/utils/colors';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import BackButton from '$lib/components/ui/BackButton.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';

	let timeline = $state<SessionTimelineResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let enabledTypes = $state<Record<string, boolean>>({});
	let expandedEntry = $state<number | null>(null);

	let sessionId = $derived($page.params.id);
	let rpSlug = $derived($page.params.rp);

	let filteredEntries = $derived(
		timeline?.entries.filter(e => enabledTypes[e.type] !== false) ?? []
	);

	onMount(async () => {
		if (!sessionId) return;
		try {
			timeline = await getSessionTimeline(sessionId);
			// Enable all types by default
			for (const type of Object.keys(timeline.entry_counts)) {
				enabledTypes[type] = true;
			}
			enabledTypes = { ...enabledTypes };
		} catch (err: any) {
			error = err.message ?? 'Failed to load timeline';
			addToast(error!, 'error');
		} finally {
			loading = false;
		}
	});

	function toggleType(type: string) {
		enabledTypes = { ...enabledTypes, [type]: !enabledTypes[type] };
	}

	function toggleAll(enable: boolean) {
		const updated: Record<string, boolean> = {};
		for (const type of Object.keys(timeline?.entry_counts ?? {})) {
			updated[type] = enable;
		}
		enabledTypes = updated;
	}

	function formatDetail(detail: Record<string, unknown>): string[] {
		const lines: string[] = [];
		for (const [key, val] of Object.entries(detail)) {
			if (val === null || val === undefined || val === '') continue;
			const label = key.replace(/_/g, ' ');
			if (Array.isArray(val)) {
				if (val.length > 0) lines.push(`${label}: ${val.join(', ')}`);
			} else {
				lines.push(`${label}: ${val}`);
			}
		}
		return lines;
	}

	function typeColor(type: string) {
		return TIMELINE_TYPE_COLORS[type] ?? { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)', dot: '#8c8176', label: type };
	}
</script>

<div class="space-y-5">
	<div class="flex items-center gap-3">
		<BackButton label="Sessions" onclick={() => goto(`/${rpSlug}/sessions`)} />
	</div>

	<PageHeader title="Session Timeline">
		{#snippet badges()}
			{#if timeline}
				<Badge>{sessionId}</Badge>
				<Badge color="var(--color-accent)" bg="var(--color-accent-soft)">
					exchanges {timeline.exchange_range[0]}–{timeline.exchange_range[1]}
				</Badge>
				<Badge>{timeline.branch}</Badge>
			{/if}
		{/snippet}
	</PageHeader>

	{#if loading}
		<div class="text-text-dim text-sm">Loading timeline...</div>
	{:else if error}
		<div class="text-error text-sm">{error}</div>
	{:else if timeline && timeline.entries.length === 0}
		<div class="bg-surface border border-border-custom rounded-lg p-8 text-center">
			<p class="text-text-dim text-sm">No events recorded for this session.</p>
		</div>
	{:else if timeline}
		<!-- Filter bar -->
		<div class="bg-surface border border-border-custom rounded-lg p-3">
			<div class="flex items-center gap-3 flex-wrap">
				<div class="flex items-center gap-2">
					<button
						class="text-[11px] font-medium text-accent hover:underline"
						onclick={() => toggleAll(true)}
					>All</button>
					<span class="text-text-dim/40">|</span>
					<button
						class="text-[11px] font-medium text-accent hover:underline"
						onclick={() => toggleAll(false)}
					>None</button>
				</div>

				{#each Object.entries(timeline.entry_counts) as [type, count]}
					{@const colors = typeColor(type)}
					<button
						class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all"
						style="background: {enabledTypes[type] !== false ? colors.bg : 'transparent'};
						       color: {enabledTypes[type] !== false ? colors.text : 'var(--color-text-dim)'};
						       opacity: {enabledTypes[type] !== false ? 1 : 0.5};
						       border: 1px solid {enabledTypes[type] !== false ? colors.dot + '30' : 'var(--color-border-custom)'};"
						onclick={() => toggleType(type)}
					>
						<span
							class="h-2 w-2 rounded-full shrink-0"
							style="background: {colors.dot};"
						></span>
						{colors.label}
						<span class="text-[10px] opacity-70">({count})</span>
					</button>
				{/each}
			</div>
		</div>

		<!-- Timeline -->
		<div class="relative pl-6">
			<!-- Vertical line -->
			<div class="absolute left-[9px] top-2 bottom-2 w-[2px] bg-border-custom rounded-full"></div>

			<div class="space-y-2">
				{#each filteredEntries as entry, idx}
					{@const colors = typeColor(entry.type)}
					<div class="relative">
						<!-- Dot on the timeline line -->
						<div
							class="absolute -left-6 top-3 h-[10px] w-[10px] rounded-full border-2 border-surface z-10"
							style="background: {colors.dot};"
						></div>

						<!-- Entry card -->
						<button
							class="w-full text-left bg-surface border border-border-custom rounded-lg px-4 py-2.5 transition-colors hover:border-accent/30"
							onclick={() => expandedEntry = expandedEntry === idx ? null : idx}
						>
							<div class="flex items-start gap-2.5">
								{#if entry.exchange_number !== null}
									<Badge
										color="var(--color-text-dim)"
										bg="var(--color-bg-subtle)"
									>#{entry.exchange_number}</Badge>
								{/if}

								<Badge
									color={colors.text}
									bg={colors.bg}
									dot={colors.dot}
								>{colors.label}</Badge>

								<span class="text-sm text-text flex-1 leading-relaxed">{entry.title}</span>

								{#if entry.characters.length > 0}
									<div class="flex items-center gap-1 shrink-0">
										{#each entry.characters.slice(0, 3) as char}
											<span class="text-[10px] px-1.5 py-0.5 rounded bg-accent/8 text-accent font-medium">
												{char}
											</span>
										{/each}
										{#if entry.characters.length > 3}
											<span class="text-[10px] text-text-dim">+{entry.characters.length - 3}</span>
										{/if}
									</div>
								{/if}
							</div>

							{#if expandedEntry === idx && Object.keys(entry.detail).length > 0}
								<div class="mt-2 pt-2 border-t border-border-custom/50 space-y-0.5">
									{#each formatDetail(entry.detail) as line}
										<p class="text-xs text-text-dim">{line}</p>
									{/each}
								</div>
							{/if}
						</button>
					</div>
				{/each}
			</div>
		</div>

		<p class="text-[11px] text-text-dim/60 text-center">
			{filteredEntries.length} of {timeline.entries.length} entries shown
		</p>
	{/if}
</div>
