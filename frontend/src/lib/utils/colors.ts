/**
 * Unified color system for the RP Engine frontend (light theme).
 * Single source of truth for card type, importance, trust stage, and significance colors.
 *
 * Each scheme has:
 *   tailwind - CSS classes for Badge bg/text
 *   hex      - raw color for canvas / SVG rendering (ForceGraph)
 *   dot      - slightly muted dot color
 */

export interface ColorScheme {
	/** Badge CSS: "bg-[...]" via inline style or Tailwind */
	bg: string;
	text: string;
	hex: string;
}

// -- Card type colors --
export const CARD_TYPE_COLORS: Record<string, ColorScheme> = {
	character:       { bg: 'rgba(139,111,192,0.12)', text: '#7c5eb8', hex: '#8b6fc0' },
	npc:             { bg: 'rgba(109,140,94,0.12)',  text: '#5a7a4d', hex: '#6d8c5e' },
	location:        { bg: 'rgba(94,130,168,0.12)',  text: '#4a7095', hex: '#5e82a8' },
	secret:          { bg: 'rgba(184,92,85,0.12)',   text: '#a04d48', hex: '#b85c55' },
	memory:          { bg: 'rgba(150,120,184,0.12)', text: '#7858a0', hex: '#9678b8' },
	knowledge:       { bg: 'rgba(184,159,106,0.12)', text: '#967e48', hex: '#b89f6a' },
	organization:    { bg: 'rgba(192,154,94,0.12)',  text: '#906e40', hex: '#c09a5e' },
	plot_thread:     { bg: 'rgba(184,126,150,0.12)', text: '#905868', hex: '#b87e96' },
	item:            { bg: 'rgba(94,168,160,0.12)',  text: '#3a8880', hex: '#5ea8a0' },
	lore:            { bg: 'rgba(120,130,184,0.12)', text: '#5860a0', hex: '#7882b8' },
	plot_arc:        { bg: 'rgba(192,126,128,0.12)', text: '#a06068', hex: '#c07e80' },
	chapter_summary: { bg: 'rgba(140,129,118,0.10)', text: '#6e6560', hex: '#8c8176' },
};

const DEFAULT_COLOR: ColorScheme = { bg: 'rgba(140,129,118,0.10)', text: '#6e6560', hex: '#8c8176' };

/** Get Badge-ready bg + text for a card type (used by Badge component inline styles) */
export function cardTypeColors(type: string): ColorScheme {
	return CARD_TYPE_COLORS[type] ?? DEFAULT_COLOR;
}

/** Legacy helper - returns inline style string. Prefer cardTypeColors() for Badge. */
export function cardTypeColor(type: string): string {
	const c = CARD_TYPE_COLORS[type] ?? DEFAULT_COLOR;
	return `color: ${c.text}; background: ${c.bg};`;
}

/** Get hex color for a card type (used in canvas rendering, e.g. ForceGraph) */
export function cardTypeHex(type: string): string {
	return (CARD_TYPE_COLORS[type] ?? DEFAULT_COLOR).hex;
}

// -- Importance colors --
export function importanceColors(imp: string | null): { bg: string; text: string } {
	if (!imp) return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
	if (imp === 'primary' || imp === 'critical' || imp === 'pov')
		return { bg: 'var(--color-accent-soft)', text: 'var(--color-accent)' };
	if (imp === 'secondary' || imp === 'main' || imp === 'recurring')
		return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text)' };
	return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
}

/** Legacy wrapper */
export function importanceColor(imp: string | null): string {
	const c = importanceColors(imp);
	return `color: ${c.text}; background: ${c.bg};`;
}

// -- Trust stage colors --
export function trustStageColors(stage: string | null): { bg: string; text: string } {
	if (!stage) return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
	const s = stage.toLowerCase();
	if (s.includes('hostile') || s.includes('enemy'))
		return { bg: 'var(--color-error-soft)', text: 'var(--color-error)' };
	if (s.includes('distrust') || s.includes('suspicious'))
		return { bg: 'var(--color-warning-soft)', text: 'var(--color-warning)' };
	if (s.includes('neutral'))
		return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
	if (s.includes('acquaint') || s.includes('friendly') || s.includes('cautious'))
		return { bg: 'var(--color-warning-soft)', text: 'var(--color-warm)' };
	if (s.includes('trust') || s.includes('ally') || s.includes('bond'))
		return { bg: 'var(--color-accent-soft)', text: 'var(--color-accent)' };
	return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
}

/** Legacy wrapper */
export function trustStageColor(stage: string | null): string {
	const c = trustStageColors(stage);
	return `color: ${c.text}; background: ${c.bg};`;
}

// -- Trust score -> color --
export function trustScoreColor(score: number): string {
	if (score >= 75) return 'var(--color-accent)';
	if (score >= 40) return 'var(--color-warm)';
	return 'var(--color-error)';
}

export function trustScoreBg(score: number): string {
	if (score >= 75) return 'var(--color-success-soft)';
	if (score >= 40) return 'var(--color-warning-soft)';
	return 'var(--color-error-soft)';
}

// -- Significance colors --
export function significanceColors(sig: string | null): { bg: string; text: string } {
	if (!sig) return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
	if (sig === 'major' || sig === 'critical')
		return { bg: 'var(--color-accent-soft)', text: 'var(--color-accent)' };
	if (sig === 'moderate')
		return { bg: 'var(--color-warning-soft)', text: 'var(--color-warm)' };
	return { bg: 'var(--color-bg-subtle)', text: 'var(--color-text-dim)' };
}

/** Legacy wrapper */
export function significanceColor(sig: string | null): string {
	const c = significanceColors(sig);
	return `color: ${c.text}; background: ${c.bg};`;
}

// -- Edge type colors for ForceGraph (muted warm palette) --
export const EDGE_TYPE_COLORS: Record<string, string> = {
	relationship: '#8b6fc0',  // purple (character)
	location:     '#5e82a8',  // steel blue
	member:       '#c09a5e',  // amber (organization)
	connection:   '#847a6e',  // warm gray
	knows_about:  '#b89f6a',  // gold (knowledge)
	belongs_to:   '#6d8c5e',  // sage (accent)
	involved_in:  '#b87e96',  // muted pink (plot_thread)
};

// Trust bar positive/negative hex
export const TRUST_COLORS = {
	positive: '#6d8c5e',  // matches --color-success
	negative: '#b85c55',  // matches --color-error
};

// Card types shown in graph filter legend
export const GRAPH_FILTER_TYPES = [
	'character', 'npc', 'location', 'secret',
	'organization', 'plot_thread', 'item', 'lore',
];

// -- Bar / progress helper --
export function barStyle(value: number, max: number): string {
	const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
	const color = pct >= 80 ? 'var(--color-error)' : pct >= 50 ? 'var(--color-warm)' : 'var(--color-accent)';
	return `width: ${pct}%; background: linear-gradient(90deg, ${color}cc, ${color});`;
}
