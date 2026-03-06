<script lang="ts">
	/**
	 * Bidirectional trust score bar with center tick and score label.
	 *
	 * Usage:
	 *   <TrustBar score={npc.trust_score} />
	 */
	import { barStyle } from '$lib/utils/format';

	interface Props {
		score: number;
	}

	let { score }: Props = $props();
</script>

<div class="flex-1 flex items-center gap-3 min-w-0">
	<div class="relative flex-1 h-2 bg-bg-subtle rounded-full overflow-hidden">
		<div class="absolute top-0 bottom-0 w-px bg-border-custom" style="left:50%"></div>
		<div class="absolute top-0 bottom-0 rounded-full" style="{barStyle(score)}"></div>
	</div>
	<span class="text-sm font-mono w-10 text-right shrink-0
		{score > 0 ? 'text-success' : score < 0 ? 'text-error' : 'text-text-dim'}">
		{score > 0 ? '+' : ''}{score}
	</span>
</div>
