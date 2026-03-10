import { apiFetch } from './client';
import type { AppConfig, ConfigUpdate, ActiveRPStatus, ProviderTestResult, DiagnosticStatus } from '$lib/types';

export type { AppConfig, ConfigUpdate, ActiveRPStatus, ProviderTestResult, DiagnosticStatus };

export async function getConfig(): Promise<AppConfig> {
	return apiFetch<AppConfig>('/api/config', { skipRPContext: true });
}

export async function updateConfig(body: ConfigUpdate): Promise<{ ok: boolean; message: string }> {
	return apiFetch('/api/config', {
		method: 'PUT',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function getActiveRP(): Promise<ActiveRPStatus> {
	return apiFetch<ActiveRPStatus>('/api/config/active-rp', { skipRPContext: true });
}

export async function setActiveRP(enabled: boolean): Promise<ActiveRPStatus> {
	return apiFetch<ActiveRPStatus>('/api/config/active-rp', {
		method: 'POST',
		body: JSON.stringify({ enabled }),
		skipRPContext: true,
	});
}

export async function testProvider(provider: string): Promise<ProviderTestResult> {
	return apiFetch<ProviderTestResult>('/api/config/test-provider', {
		params: { provider },
		skipRPContext: true,
	});
}

// Diagnostics API

export async function getDiagnosticStatus(): Promise<DiagnosticStatus> {
	return apiFetch<DiagnosticStatus>('/api/diagnostics', { skipRPContext: true });
}

export async function updateDiagnostics(body: Record<string, unknown>): Promise<{ ok: boolean; warning?: string }> {
	return apiFetch('/api/diagnostics', {
		method: 'PUT',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function clearDiagnostics(): Promise<{ ok: boolean; files_removed: number }> {
	return apiFetch('/api/diagnostics', {
		method: 'DELETE',
		skipRPContext: true,
	});
}

export async function downloadDiagnostics(): Promise<void> {
	const resp = await fetch('/api/diagnostics/download');
	if (!resp.ok) throw new Error('Download failed');
	const blob = await resp.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'diagnostics.zip';
	a.click();
	URL.revokeObjectURL(url);
}

export async function sendDiagnosticReport(): Promise<{ ok: boolean; error?: string }> {
	return apiFetch('/api/diagnostics/report', {
		method: 'POST',
		skipRPContext: true,
	});
}
