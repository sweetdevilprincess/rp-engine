export interface CustomStateSchema {
	id: string;
	rp_folder: string | null;
	category: string;
	name: string;
	data_type: string;
	config: Record<string, unknown> | null;
	belongs_to: string | null;
	inject_as: string;
	display_order: number;
}

export interface CustomStateValue {
	schema_id: string;
	entity_id: string | null;
	value: unknown;
	exchange_number: number | null;
	changed_by: string | null;
	reason: string | null;
}

export interface CustomStateSnapshot {
	schemas: CustomStateSchema[];
	values: CustomStateValue[];
}

export interface PresetInfo {
	name: string;
	description: string | null;
	schema_count: number;
}
