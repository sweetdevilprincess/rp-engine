/** NPC archetypes used in the RP Engine trust framework. */
export const ARCHETYPES = [
	{ value: '', label: '(none)' },
	{ value: 'POWER_HOLDER', label: 'Power Holder' },
	{ value: 'TRANSACTIONAL', label: 'Transactional' },
	{ value: 'COMMON_PEOPLE', label: 'Common People' },
	{ value: 'OPPOSITION', label: 'Opposition' },
	{ value: 'SPECIALIST', label: 'Specialist' },
	{ value: 'PROTECTOR', label: 'Protector' },
	{ value: 'OUTSIDER', label: 'Outsider' },
];

/** Short descriptions for each archetype (shown in tooltips). */
export const ARCHETYPE_DESCRIPTIONS: Record<string, string> = {
	POWER_HOLDER: 'Authority figure — trust tied to respect for their power and status',
	TRANSACTIONAL: 'Deal-maker — trust earned through fair exchanges and mutual benefit',
	COMMON_PEOPLE: 'Everyday folk — trust builds through kindness, reliability, and community',
	OPPOSITION: 'Adversary — trust requires proving you\'re not a threat to their goals',
	SPECIALIST: 'Expert — trust comes from respecting their craft and competence',
	PROTECTOR: 'Guardian — trust earned by showing you share their protective values',
	OUTSIDER: 'Loner or misfit — trust is slow, built through patience and acceptance',
};

/** Behavioral modifiers that alter NPC trust dynamics. */
export const MODIFIERS = [
	'OBSESSIVE',
	'SADISTIC',
	'PARANOID',
	'FANATICAL',
	'NARCISSISTIC',
	'SOCIOPATHIC',
	'ADDICTED',
	'HONOR_BOUND',
	'GRIEF_CONSUMED',
];

/** Short descriptions for each modifier (shown in tooltips). */
export const MODIFIER_DESCRIPTIONS: Record<string, string> = {
	OBSESSIVE: 'Pathological fixation on a target — overrides all behavior when fixation is involved',
	SADISTIC: 'Cruelty is the goal, not just a means — seeks opportunities to cause suffering',
	PARANOID: 'Extreme distrust colors all interactions — assumes the worst, guards everything',
	FANATICAL: 'Ideology overrides survival and self-interest — the cause is everything',
	NARCISSISTIC: 'Ego and admiration needs drive behavior — cannot admit fault or share spotlight',
	SOCIOPATHIC: 'Pure calculation, no genuine emotions — every relationship is strategic',
	ADDICTED: 'Substance or behavior dependency — dominates during craving, dormant when satisfied',
	HONOR_BOUND: 'Code or oath overrides self-interest — breaking their word is worse than death',
	GRIEF_CONSUMED: 'Temporary — overwhelming loss drives reckless or self-destructive behavior',
};
