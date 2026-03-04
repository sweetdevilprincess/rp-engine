<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import Sidebar from '$lib/components/nav/Sidebar.svelte';
	import ToastContainer from '$lib/components/ui/ToastContainer.svelte';
	import { rpList } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import { checkHealth } from '$lib/api/health';
	import { listRPs } from '$lib/api/rp';

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

	onMount(() => {
		refreshHealth();
		refreshRPs();
		const interval = setInterval(refreshHealth, 30000);
		return () => clearInterval(interval);
	});
</script>

<div class="flex h-screen overflow-hidden">
	<Sidebar />
	<main class="flex-1 overflow-y-auto p-6">
		<slot />
	</main>
</div>

<ToastContainer />
