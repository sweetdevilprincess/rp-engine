<script lang="ts">
	import type { CardType } from '$lib/types';

	export let type: CardType;
	export let size: 'sm' | 'md' = 'sm';

	const colorMap: Record<string, string> = {
		character: 'bg-purple-500/20 text-purple-400',
		npc: 'bg-purple-500/20 text-purple-400',
		location: 'bg-blue-500/20 text-blue-400',
		secret: 'bg-red-500/20 text-red-400',
		memory: 'bg-amber-500/20 text-amber-400',
		knowledge: 'bg-amber-500/20 text-amber-400',
		organization: 'bg-green-500/20 text-green-400',
		plot_thread: 'bg-orange-500/20 text-orange-400',
		plot_arc: 'bg-orange-500/20 text-orange-400',
		item: 'bg-cyan-500/20 text-cyan-400',
		lore: 'bg-indigo-500/20 text-indigo-400',
		chapter_summary: 'bg-gray-500/20 text-gray-400',
	};

	$: classes = colorMap[type] ?? 'bg-gray-500/20 text-gray-400';
	$: sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm';
</script>

<span class="inline-flex items-center rounded-full font-medium {classes} {sizeClasses}">
	{type.replace('_', ' ')}
</span>
