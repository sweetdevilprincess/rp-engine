export interface TrustShift {
  direction: 'increase' | 'decrease' | 'neutral';
  amount: number;
  reason: string | null;
}
export interface NPCReaction {
  character: string;
  internalMonologue: string;
  physicalAction: string;
  dialogue: string | null;
  emotionalUndercurrent: string;
  trustShift: TrustShift;
}
export interface TrustEvent {
  date: string;
  change: number;
  direction: string;
  reason: string | null;
}
export interface TrustInfo {
  npc_name: string;
  target: string;
  trust_score: number;
  trust_stage: string;
  session_gains: number;
  session_losses: number;
  history: TrustEvent[];
}
export interface NPCListItem {
  name: string;
  importance: string | null;
  primary_archetype: string | null;
  secondary_archetype: string | null;
  behavioral_modifiers: string[];
  trust_score: number;
  trust_stage: string;
  location: string | null;
  emotional_state: string | null;
}
export interface NPCBrief {
  character: string;
  importance: string | null;
  archetype: string | null;
  secondary_archetype: string | null;
  behavioral_modifiers: string[];
  trust_score: number;
  trust_stage: string | null;
  emotional_state: string | null;
  conditions: string[];
  behavioral_direction: string;
  scene_signals: string[];
}
