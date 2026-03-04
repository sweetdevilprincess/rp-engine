export interface ExchangeSave {
  user_message: string;
  assistant_response: string;
  exchange_number?: number;
  idempotency_key?: string;
  parent_exchange_number?: number;
  session_id?: string;
  in_story_timestamp?: string;
  location?: string;
  metadata?: Record<string, unknown>;
}
export interface ExchangeResponse {
  id: number;
  exchange_number: number;
  session_id: string;
  created_at: string;
  analysis_status: string;
  rewound_count: number | null;
  idempotent_hit: boolean | null;
}
export interface ExchangeDetail {
  id: number;
  exchange_number: number;
  session_id: string;
  user_message: string;
  assistant_response: string;
  in_story_timestamp: string | null;
  location: string | null;
  npcs_involved: string[] | null;
  analysis_status: string;
  created_at: string;
  metadata: Record<string, unknown> | null;
}
export interface ExchangeListResponse {
  exchanges: ExchangeDetail[];
  total_count: number;
}
