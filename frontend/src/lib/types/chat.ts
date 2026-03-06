export interface ChatMessage {
	role: 'user' | 'assistant';
	content: string;
	timestamp: string;
}

export interface ChatResponse {
	response: string;
	model_used: string;
}
