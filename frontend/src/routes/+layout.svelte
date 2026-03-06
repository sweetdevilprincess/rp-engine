<script lang="ts">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';
	import '../app.css';
	import Header from '$lib/components/nav/Header.svelte';
	import Footer from '$lib/components/nav/Footer.svelte';
	import ToastContainer from '$lib/components/ui/ToastContainer.svelte';
	import { rpList } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import { checkHealth } from '$lib/api/health';
	import { listRPs } from '$lib/api/rp';

	interface Props {
		children?: Snippet;
	}

	let { children }: Props = $props();

	let scrolled = $state(false);
	let mainEl: HTMLElement;

	function handleScroll() {
		scrolled = mainEl ? mainEl.scrollTop > 20 : false;
	}

	async function refreshHealth() {
		try {
			const data = await checkHealth();
			serverHealth.set({ status: 'online', data });
		} catch {
			serverHealth.set({ status: 'offline', data: null });
		}
	}

	async function refreshRPs() {
		try {
			const rps = await listRPs();
			rpList.set(rps);
		} catch {}
	}

	function loadAppearance() {
		try {
			const stored = localStorage.getItem('rp-appearance');
			if (!stored) return;
			const prefs = JSON.parse(stored);
			const root = document.documentElement;
			if (prefs.accentColor) root.style.setProperty('--color-accent', prefs.accentColor);
			const fontSizes: Record<string, string> = { small: '13px', medium: '14px', large: '16px' };
			if (prefs.fontSize && fontSizes[prefs.fontSize]) root.style.setProperty('font-size', fontSizes[prefs.fontSize]);
		} catch {}
	}

	onMount(() => {
		loadAppearance();
		refreshHealth();
		refreshRPs();
		const interval = setInterval(refreshHealth, 30000);
		return () => clearInterval(interval);
	});
</script>

<div class="flex flex-col min-h-screen bg-bg">
	<Header {scrolled} />
	<main
		bind:this={mainEl}
		onscroll={handleScroll}
		class="flex-1 overflow-y-auto p-5"
	>
		{@render children?.()}
	</main>
	<Footer />
</div>

<ToastContainer />
