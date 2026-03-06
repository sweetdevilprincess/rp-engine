export interface AppConfig {
	server: { host: string; port: number; cors_origins: string[] };
	paths: { vault_root: string; db_path: string };
	llm: {
		provider: string;
		api_key: string;
		models: {
			npc_reactions: string;
			response_analysis: string;
			card_generation: string;
			embeddings: string;
		};
		fallback_model: string;
	};
	context: { max_documents: number; max_graph_hops: number; stale_threshold_turns: number };
	search: {
		vector_weight: number;
		bm25_weight: number;
		similarity_threshold: number;
		chunk_size: number;
		chunk_overlap: number;
	};
	trust: {
		increase_value: number;
		decrease_value: number;
		session_max_gain: number;
		session_max_loss: number;
		min_score: number;
		max_score: number;
	};
	rp: { default_pov_character: string };
}

export interface ConfigUpdate {
	server?: Partial<AppConfig['server']>;
	paths?: Partial<AppConfig['paths']>;
	llm?: Partial<AppConfig['llm']>;
	context?: Partial<AppConfig['context']>;
	search?: Partial<AppConfig['search']>;
	trust?: Partial<AppConfig['trust']>;
	rp?: Partial<AppConfig['rp']>;
	openrouter_api_key?: string;
}

export interface ActiveRPStatus {
	active_rp: boolean;
	session_count: number;
}
