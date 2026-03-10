export interface BranchCreate {
  name: string;
  rp_folder: string;
  description?: string;
  branch_from?: string;
  branch_point_exchange?: number;
}
export interface BranchInfo {
  name: string;
  rp_folder: string;
  created_from: string | null;
  branch_point_session: string | null;
  branch_point_exchange: number | null;
  description: string | null;
  is_active: boolean;
  is_archived: boolean;
  created_at: string | null;
  exchange_count: number;
}
export interface BranchListResponse {
  active_branch: string | null;
  branches: BranchInfo[];
}
export interface BranchSwitchRequest {
  name: string;
}
export interface BranchSwitchResponse {
  active_branch: string;
  previous_branch: string | null;
}
export interface CheckpointCreate {
  name: string;
  description?: string;
}
export interface CheckpointInfo {
  name: string;
  branch: string;
  exchange_number: number;
  description: string | null;
  created_at: string;
}
export interface CheckpointRestoreRequest {
  checkpoint_name: string;
}
export interface CheckpointRestoreResponse {
  restored_from: string;
  exchange_number: number;
  new_branch: string | null;
  rewound_count: number | null;
}
