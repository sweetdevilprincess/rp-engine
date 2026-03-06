<script lang="ts">
	/**
	 * Backwards-compatible wrapper around Badge for card type display.
	 * Existing pages can keep using <TypeBadge type={card.card_type} />
	 * without changes. New code should prefer <Badge> directly.
	 */
	import type { CardType } from '$lib/types';
	import { cardTypeColors } from '$lib/utils/colors';
	import Badge from './Badge.svelte';

	interface Props {
		type: CardType;
		size?: 'sm' | 'md';
	}

	let { type, size = 'sm' }: Props = $props();

	let colors = $derived(cardTypeColors(type));
</script>

<Badge color={colors.text} bg={colors.bg} dot={colors.hex}>
	{type.replace('_', ' ')}
</Badge>
