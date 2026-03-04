export interface ThreadDetail {
  thread_id: string;
  name: string;
  thread_type: string | null;
  priority: string | null;
  status: string;
  keywords: string[];
  current_counter: number;
  thresholds: Record<string, number>;
  consequences: Record<string, string>;
  related_characters: string[];
}
export interface ThreadListResponse {
  threads: ThreadDetail[];
  total: number;
}
export interface ThreadCounterUpdate {
  counter: number;
}
