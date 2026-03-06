export interface AuditGap {
	entity_name: string;
	suggested_type: string | null;
	mention_count: number;
	exchanges: number[];
}
export interface AuditResponse {
	mode: string;
	gaps: AuditGap[];
	total_exchanges_scanned: number;
	total_gaps: number;
}
