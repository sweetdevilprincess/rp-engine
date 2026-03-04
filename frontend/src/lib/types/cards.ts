export interface StoryCardSummary {
  name: string;
  card_type: string;
  importance: string | null;
  file_path: string;
  summary: string | null;
  aliases: string[];
  tags: string[];
}
export interface EntityConnection {
  to_entity: string;
  connection_type: string;
  field: string | null;
  role: string | null;
}
export interface StoryCardDetail {
  name: string;
  card_type: string;
  file_path: string;
  importance: string | null;
  frontmatter: Record<string, unknown>;
  content: string;
  connections: EntityConnection[];
}
export interface StoryCardCreate {
  name: string;
  frontmatter?: Record<string, unknown>;
  content?: string;
}
export interface StoryCardUpdate {
  frontmatter?: Record<string, unknown>;
  content?: string;
}
export interface CardListResponse {
  cards: StoryCardSummary[];
  total: number;
}
export interface ReindexResponse {
  entities: number;
  connections: number;
  aliases: number;
  keywords: number;
  duration_ms: number;
}
