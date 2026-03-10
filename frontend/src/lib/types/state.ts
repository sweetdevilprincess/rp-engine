export interface CharacterDetail {
	name: string;
	card_path: string | null;
	is_player_character: boolean;
	importance: string | null;
	primary_archetype: string | null;
	secondary_archetype: string | null;
	behavioral_modifiers: string[];
	location: string | null;
	conditions: string[];
	emotional_state: string | null;
	last_seen: string | null;
	updated_at: string | null;
}
export interface TrustModification {
	date: string | null;
	change: number;
	direction: string;
	reason: string | null;
	exchange_id: number | null;
	branch: string | null;
	exchange_number: number | null;
}
export interface RelationshipDetail {
	character_a: string;
	character_b: string;
	initial_trust_score: number;
	trust_modification_sum: number;
	live_trust_score: number;
	trust_stage: string;
	dynamic: string | null;
	modifications: TrustModification[];
}
export interface EventDetail {
	id: number;
	in_story_timestamp: string | null;
	event: string;
	characters: string[];
	significance: string | null;
	exchange_id: number | null;
	created_at: string | null;
}
export interface SceneStateDetail {
	location: string | null;
	time_of_day: string | null;
	mood: string | null;
	in_story_timestamp: string | null;
}
export interface StateSnapshot {
	characters: Record<string, CharacterDetail>;
	relationships: RelationshipDetail[];
	scene: SceneStateDetail;
	events: EventDetail[];
	session: Record<string, unknown> | null;
	branch: string;
}
export interface RelGraphNode {
	name: string;
	is_player_character: boolean;
	importance: string | null;
	primary_archetype: string | null;
	trust_score: number;
	trust_stage: string;
	emotional_state: string | null;
	location: string | null;
}
export interface RelGraphEdge {
	from_char: string;
	to_char: string;
	trust_score: number;
	trust_stage: string;
	dynamic: string | null;
	trend: 'rising' | 'falling' | 'stable';
	modification_count: number;
}
export interface RelationshipGraphResponse {
	nodes: RelGraphNode[];
	edges: RelGraphEdge[];
	metadata: { total_npcs: number; total_edges: number };
}
