export interface SessionCreate {
  rp_folder: string;
  branch?: string;
}
export interface SessionResponse {
  id: string;
  rp_folder: string;
  branch: string;
  started_at: string;
  ended_at: string | null;
  metadata: Record<string, unknown> | null;
}
export interface TrustChange {
  npc: string;
  delta: number;
  reason: string;
}
export interface NewEntity {
  name: string;
  type: string;
  first_mention_exchange: number | null;
}
export interface RelationshipArc {
  characters: string[];
  arc_summary: string;
}
export interface CharacterStateChange {
  character: string;
  field: string;
  old_value: string | null;
  new_value: string | null;
}
export interface SceneProgression {
  first_timestamp: string | null;
  last_timestamp: string | null;
  locations_visited: string[];
}
export interface PlotThreadStatus {
  thread_id: string;
  name: string;
  start_counter: number;
  end_counter: number;
}
export interface SessionEndSummary {
  significant_events: string[];
  trust_changes: TrustChange[];
  new_entities: NewEntity[];
  relationship_arcs: RelationshipArc[];
  character_state_changes: CharacterStateChange[];
  scene_progression: SceneProgression | null;
  plot_thread_status: PlotThreadStatus[];
}
export interface SessionEndResponse {
  session: SessionResponse;
  summary: SessionEndSummary;
}
