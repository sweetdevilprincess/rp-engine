<!--
  Uppercase tracking label used as section/group headers.
  Usage: <SectionLabel>Story Bible</SectionLabel>
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		children?: Snippet;
	}

	let { children }: Props = $props();
</script>

<span class="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">
	{@render children?.()}
</span>
