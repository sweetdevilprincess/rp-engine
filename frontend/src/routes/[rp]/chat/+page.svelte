<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { activeRP } from '$lib/stores/rp';
	import { addToast } from '$lib/stores/ui';
	import { getFullState } from '$lib/api/state';
	import { sendChatMessage, type ChatMessage } from '$lib/api/chat';
	import type { StateSnapshot } from '$lib/types';
	import Btn from '$lib/components/ui/Btn.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import SectionLabel from '$lib/components/ui/SectionLabel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import InfoRow from '$lib/components/ui/InfoRow.svelte';

	// ── Chat state ────────────────────────────────────────────
	let messages: ChatMessage[] = $state([]);
	let userInput = $state('');
	let sending = $state(false);
	let chatLog: HTMLDivElement;

	// ── Stats panel ───────────────────────────────────────────
	let showStats = $state(true);
	let stateSnapshot: StateSnapshot | null = $state(null);
	let loadingState = $state(false);

	const STORAGE_KEY = 'rp-chat-messages';

	onMount(async () => {
		// Restore chat history from sessionStorage
		try {
			const stored = sessionStorage.getItem(STORAGE_KEY);
			if (stored) messages = JSON.parse(stored);
		} catch {}
		await loadState();
	});

	$effect(() => {
		// Persist chat history on change
		try {
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
		} catch {}
	});

	async function loadState() {
		loadingState = true;
		try {
			stateSnapshot = await getFullState();
		} catch {
			// Stats panel is optional — don't fail the page
		} finally {
			loadingState = false;
		}
	}

	async function handleSend() {
		const msg = userInput.trim();
		if (!msg || sending) return;

		// Add user message
		messages = [...messages, { role: 'user', content: msg, timestamp: new Date().toISOString() }];
		userInput = '';
		sending = true;

		await tick();
		scrollToBottom();

		try {
			const result = await sendChatMessage(msg);
			messages = [...messages, { role: 'assistant', content: result.response, timestamp: new Date().toISOString() }];
			// Refresh state after each exchange
			loadState();
		} catch (e: any) {
			addToast(e.message ?? 'Chat failed', 'error');
		} finally {
			sending = false;
			await tick();
			scrollToBottom();
		}
	}

	function scrollToBottom() {
		if (chatLog) chatLog.scrollTop = chatLog.scrollHeight;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function fmt(iso: string) {
		return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
	}
</script>

<div class="relative h-[calc(100vh-160px)] flex flex-col bg-surface border border-border-custom rounded-lg overflow-hidden">

	<!-- Floating stats panel (top-left overlay) -->
	{#if showStats}
		<div class="absolute top-[50px] left-3 z-10 bg-surface/95 backdrop-blur-sm border border-border-custom rounded-[10px] shadow-lg w-56 max-h-[70%] overflow-y-auto">
			<div class="px-3 py-2.5 border-b border-border-custom flex items-center justify-between sticky top-0 bg-surface/95 backdrop-blur-sm">
				<SectionLabel>Stats</SectionLabel>
				<button
					class="text-xs text-text-dim hover:text-text transition-colors"
					onclick={() => (showStats = false)}
				>Hide</button>
			</div>
			<div class="p-3 space-y-3">
				{#if loadingState}
					<p class="text-xs text-text-dim">Loading...</p>
				{:else if stateSnapshot}
					<!-- Scene -->
					<div>
						<div class="mb-1"><SectionLabel>Scene</SectionLabel></div>
						<div class="space-y-1 text-xs">
							{#if stateSnapshot.scene.location}
								<InfoRow label="Location" value={stateSnapshot.scene.location} />
							{/if}
							{#if stateSnapshot.scene.time_of_day}
								<InfoRow label="Time" value={stateSnapshot.scene.time_of_day} />
							{/if}
							{#if stateSnapshot.scene.mood}
								<InfoRow label="Mood" value={stateSnapshot.scene.mood} />
							{/if}
						</div>
					</div>

					<!-- Characters -->
					{#if Object.keys(stateSnapshot.characters).length > 0}
						<div>
							<div class="mb-1"><SectionLabel>Characters</SectionLabel></div>
							<div class="space-y-1.5">
								{#each Object.entries(stateSnapshot.characters) as [name, char]}
									<div class="text-xs">
										<span class="text-text font-medium">{name}</span>
										{#if char.emotional_state}
											<span class="text-text-dim italic ml-1">{char.emotional_state}</span>
										{/if}
										{#if char.conditions.length > 0}
											<div class="flex flex-wrap gap-0.5 mt-0.5">
												{#each char.conditions as cond}
													<span class="bg-bg-subtle px-1 py-0.5 rounded text-[10px] text-text-dim">{cond}</span>
												{/each}
											</div>
										{/if}
									</div>
								{/each}
							</div>
						</div>
					{/if}
				{:else}
					<p class="text-xs text-text-dim">No state data available.</p>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Header -->
	<div class="px-4 py-2.5 border-b border-border-custom shrink-0">
		<PageHeader title={$activeRP?.rp_folder ?? 'Chat'} size="sm">
			{#snippet before()}
				<button
					class="text-xs px-2 py-1 rounded transition-colors {showStats
						? 'bg-accent/20 text-accent'
						: 'text-text-dim hover:text-text'}"
					onclick={() => (showStats = !showStats)}
				>Stats</button>
			{/snippet}
			{#snippet badges()}
				<span class="text-xs text-text-dim">
					{messages.length} message{messages.length !== 1 ? 's' : ''}
				</span>
			{/snippet}
			{#snippet actions()}
				<Badge>stub mode</Badge>
			{/snippet}
		</PageHeader>
	</div>

	<!-- Chat log (centered) -->
	<div
		bind:this={chatLog}
		class="flex-1 overflow-y-auto p-4"
	>
		<div class="max-w-[620px] mx-auto space-y-4">
			{#if messages.length === 0}
				<div class="flex items-center justify-center h-full text-sm text-text-dim" style="min-height: 200px">
					Start a conversation. Type a message below.
				</div>
			{:else}
				{#each messages as msg}
					<div class="flex gap-3 {msg.role === 'user' ? 'justify-end' : ''}">
						{#if msg.role === 'user'}
							<div class="max-w-[80%] bg-gradient-to-br from-accent/10 to-accent/5 border border-accent/20 rounded-[14px] rounded-br-[4px] px-4 py-3">
								<p class="text-sm text-text whitespace-pre-wrap">{msg.content}</p>
								<p class="text-[10px] text-text-dim mt-1.5">{fmt(msg.timestamp)}</p>
							</div>
						{:else}
							<div class="max-w-[80%] bg-white border border-border-custom/50 rounded-[14px] rounded-bl-[4px] px-4 py-3 shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
								<p class="text-sm text-text whitespace-pre-wrap font-serif">{msg.content}</p>
								<p class="text-[10px] text-text-dim mt-1.5">{fmt(msg.timestamp)}</p>
							</div>
						{/if}
					</div>
				{/each}
				{#if sending}
					<div class="flex gap-3">
						<div class="bg-white border border-border-custom/50 rounded-[14px] rounded-bl-[4px] px-4 py-3 shadow-[0_1px_4px_rgba(0,0,0,0.04)]">
							<p class="text-sm text-text-dim animate-pulse font-serif">Generating...</p>
						</div>
					</div>
				{/if}
			{/if}
		</div>
	</div>

	<!-- Input bar (centered) -->
	<div class="border-t border-border-custom shrink-0">
		<div class="max-w-[620px] mx-auto px-4 py-3 flex items-end gap-2">
			<textarea
				bind:value={userInput}
				onkeydown={handleKeydown}
				placeholder="Type a message..."
				rows="1"
				class="flex-1 bg-bg-subtle border border-border-custom rounded-lg px-3 py-2 text-sm text-text
					placeholder:text-text-dim/50 focus:outline-none focus:ring-1 focus:ring-accent resize-none
					max-h-32 overflow-y-auto"
			></textarea>
			<Btn primary onclick={handleSend} disabled={sending || !userInput.trim()}>
				Send
			</Btn>
		</div>
	</div>
</div>
