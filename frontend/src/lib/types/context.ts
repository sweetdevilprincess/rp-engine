import type { NPCBrief, NPCReaction } from './npc';
import type { GuidelinesResponse } from './rp';

export interface ContextRequest {
  user_message: string;
  last_response?: string;
  include_npc_reactions?: boolean;
}
export interface ContextDocument {
  name: string;
  card_type: string;
  file_path: string;
  source: 'keyword' | 'semantic' | 'graph' | 'trigger' | 'always_load';
  relevance_score: number;
  content: string | null;
  summary: string | null;
  status: 'new' | 'updated';
}
export interface ContextReference {
  name: string;
  card_type: string;
  status: 'already_loaded';
  sent_at_turn: number;
}
export interface FlaggedNPC {
  character: string;
  importance: string | null;
  reason: string;
}
export interface SceneState {
  location: string | null;
  time_of_day: string | null;
  mood: string | null;
  in_story_timestamp: string | null;
}
export interface CharacterState {
  location: string | null;
  conditions: string[];
  emotional_state: string | null;
}
export interface ThreadAlert {
  thread_id: string;
  name: string;
  level: 'gentle' | 'moderate' | 'strong';
  counter: number;
  threshold: number;
  consequence: string;
}
export interface TriggeredNote {
  trigger_id: string;
  trigger_name: string;
  inject_type: 'context_note' | 'state_alert';
  content: string;
  priority: number;
  signals_matched: string[];
}
export interface CardGap {
  entity_name: string;
  seen_count: number;
  suggested_type: string | null;
}
export interface StalenessWarning {
  type: string;
  exchange: number;
  failed_at: string;
  stale_fields: string[];
}
export interface WritingConstraints {
  text: string;
  patterns_included: string[];
  task_context: string;
  token_count: number;
}
export interface ResolveRequest {
  scene_description: string;
  keywords?: string[];
  max_hops?: number;
  max_results?: number;
}
export interface ContextResponse {
  current_exchange: number;
  documents: ContextDocument[];
  references: ContextReference[];
  npc_briefs: NPCBrief[];
  npc_reactions: NPCReaction[];
  flagged_npcs: FlaggedNPC[];
  guidelines: GuidelinesResponse | null;
  scene_state: SceneState;
  character_states: Record<string, CharacterState>;
  thread_alerts: ThreadAlert[];
  triggered_notes: TriggeredNote[];
  card_gaps: CardGap[];
  warnings: StalenessWarning[];
  writing_constraints: WritingConstraints | null;
}
