import { apiFetch } from './client';
import type { ChatResponse } from '$lib/types';

export type { ChatMessage, ChatResponse } from '$lib/types';

export async function sendChatMessage(message: string): Promise<ChatResponse> {
	try {
		return await apiFetch<ChatResponse>('/api/chat', {
			method: 'POST',
			body: JSON.stringify({ user_message: message }),
		});
	} catch (err: any) {
		// Stub fallback when backend endpoint doesn't exist yet
		if (err.status === 404 || err.status === 405) {
			await new Promise(r => setTimeout(r, 1500));
			return {
				response: `[Stub response — /api/chat not yet implemented]\n\nYou said: "${message.slice(0, 100)}"\n\nThis is a placeholder response. The chat endpoint will be built when local model support is added.`,
				model_used: 'stub',
			};
		}
		throw err;
	}
}
