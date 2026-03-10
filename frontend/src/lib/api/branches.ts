import { apiFetch } from './client';
import type { BranchCreate, BranchInfo, BranchListResponse, BranchSwitchResponse, CheckpointInfo, CheckpointRestoreResponse } from '$lib/types';

export async function listBranches(rp_folder: string): Promise<BranchListResponse> {
	return apiFetch<BranchListResponse>('/api/branches', {
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function getBranch(name: string, rp_folder: string): Promise<BranchInfo> {
	return apiFetch<BranchInfo>(`/api/branches/${encodeURIComponent(name)}`, {
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function createBranch(body: BranchCreate): Promise<BranchInfo> {
	return apiFetch<BranchInfo>('/api/branches', {
		method: 'POST',
		body: JSON.stringify(body),
		skipRPContext: true,
	});
}

export async function switchBranch(name: string, rp_folder: string): Promise<BranchSwitchResponse> {
	return apiFetch<BranchSwitchResponse>('/api/branches/active', {
		method: 'PUT',
		body: JSON.stringify({ name }),
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function archiveBranch(name: string, rp_folder: string, archived = true): Promise<BranchInfo> {
	return apiFetch<BranchInfo>(`/api/branches/${encodeURIComponent(name)}/archive`, {
		method: 'PATCH',
		body: JSON.stringify({ archived }),
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function listCheckpoints(branch_name: string, rp_folder: string): Promise<CheckpointInfo[]> {
	return apiFetch<CheckpointInfo[]>(`/api/branches/${encodeURIComponent(branch_name)}/checkpoints`, {
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function createCheckpoint(branch_name: string, rp_folder: string, name: string, description?: string): Promise<CheckpointInfo> {
	return apiFetch<CheckpointInfo>(`/api/branches/${encodeURIComponent(branch_name)}/checkpoint`, {
		method: 'POST',
		body: JSON.stringify({ name, description }),
		params: { rp_folder },
		skipRPContext: true,
	});
}

export async function restoreCheckpoint(branch_name: string, rp_folder: string, checkpoint_name: string): Promise<CheckpointRestoreResponse> {
	return apiFetch<CheckpointRestoreResponse>(`/api/branches/${encodeURIComponent(branch_name)}/restore`, {
		method: 'POST',
		body: JSON.stringify({ checkpoint_name }),
		params: { rp_folder },
		skipRPContext: true,
	});
}
