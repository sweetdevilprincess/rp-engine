export interface GraphNode {
	name: string;
	card_type: string;
	importance: string;
}
export interface GraphEdge {
	from: string;
	to: string;
	connection_type: string;
}
export interface GraphData {
	nodes: GraphNode[];
	edges: GraphEdge[];
}
