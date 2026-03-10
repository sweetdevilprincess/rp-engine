/**
 * Shared formatting utilities.
 */

import { TRUST_COLORS } from './colors';

/** Format ISO date string to short locale form (e.g. "Mar 4") */
export function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Format ISO date string to short time form (e.g. "2:30 PM") */
export function formatTime(iso: string): string {
	return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

/** Trust bar inline style: range -100 to +100, centered at 50% */
export function barStyle(score: number): string {
	const clamped = Math.max(-100, Math.min(100, score));
	const width = Math.abs(clamped) / 2;
	const left = clamped >= 0 ? 50 : 50 + clamped / 2;
	const color = clamped >= 0 ? TRUST_COLORS.positive : TRUST_COLORS.negative;
	return `left:${left}%;width:${width}%;background:${color}`;
}
