export interface RPCreate {
  rp_name: string;
  pov_mode?: 'single' | 'dual';
  dual_characters?: string[];
  tone?: string;
  scene_pacing?: 'slow' | 'moderate' | 'fast';
}
export interface RPResponse {
  rp_folder: string;
  created_files: string[];
}
export interface RPInfo {
  rp_folder: string;
  has_story_cards: boolean;
  card_count: number;
  has_guidelines: boolean;
  branches: string[];
}
export interface GuidelinesResponse {
  pov_mode: 'single' | 'dual' | null;
  dual_characters: string[];
  narrative_voice: 'first' | 'third' | null;
  tense: 'present' | 'past' | null;
  tone: string[] | string | null;
  scene_pacing: 'slow' | 'moderate' | 'fast' | null;
  integrate_user_narrative: boolean | null;
  pov_character: string | null;
  preserve_user_details: boolean | null;
  sensitive_themes: string[];
  hard_limits: string | string[] | null;
  response_length: 'short' | 'medium' | 'long' | null;
}
