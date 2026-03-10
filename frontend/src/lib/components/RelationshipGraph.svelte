<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import type { RelationshipGraphResponse, RelGraphNode, RelGraphEdge } from '$lib/types';

	interface Props {
		data: RelationshipGraphResponse;
		onNodeClick?: ((node: RelGraphNode) => void) | null;
	}

	let { data, onNodeClick = null }: Props = $props();

	let container: HTMLDivElement;
	let graph: any = null;
	let resizeObserver: ResizeObserver | null = null;

	// Trust stage → color mapping
	function trustColor(score: number): string {
		if (score >= 20) return '#6d8c5e';   // success green
		if (score >= 5) return '#8ab47a';     // light green
		if (score >= -5) return '#b0a698';    // warm gray
		if (score >= -20) return '#c4956a';   // warm orange
		return '#b85c55';                      // error red
	}

	function nodeColor(node: RelGraphNode): string {
		if (node.is_player_character) return '#b89f6a'; // gold for PC
		return trustColor(node.trust_score);
	}

	function nodeSize(node: RelGraphNode): number {
		if (node.is_player_character) return 10;
		const imp = node.importance?.toLowerCase() ?? '';
		if (imp === 'primary' || imp === 'critical' || imp === 'pov') return 8;
		if (imp === 'secondary' || imp === 'main' || imp === 'recurring') return 6;
		return 4;
	}

	interface ForceNode {
		id: string;
		nodeData: RelGraphNode;
		x?: number;
		y?: number;
	}
	interface ForceLink {
		source: string;
		target: string;
		edgeData: RelGraphEdge;
	}

	function buildGraphData(d: RelationshipGraphResponse) {
		const forceNodes: ForceNode[] = d.nodes.map(n => ({
			id: n.name,
			nodeData: n,
		}));
		const nodeNames = new Set(d.nodes.map(n => n.name));
		const forceLinks: ForceLink[] = d.edges
			.filter(e => nodeNames.has(e.from_char) && nodeNames.has(e.to_char))
			.map(e => ({
				source: e.from_char,
				target: e.to_char,
				edgeData: e,
			}));
		return { nodes: forceNodes, links: forceLinks };
	}

	async function initGraph() {
		if (!container) return;
		const ForceGraph2D = (await import('force-graph')).default as any;

		const { nodes, links } = buildGraphData(data);

		graph = ForceGraph2D()(container)
			.graphData({ nodes, links })
			.nodeId('id')
			.nodeLabel((n: ForceNode) => {
				const nd = n.nodeData;
				let label = nd.name;
				if (nd.trust_stage && nd.trust_stage !== 'neutral') label += ` (${nd.trust_stage})`;
				if (nd.emotional_state) label += `\n${nd.emotional_state}`;
				return label;
			})
			.nodeCanvasObject((n: ForceNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
				const nd = n.nodeData;
				const size = nodeSize(nd);
				const color = nodeColor(nd);
				const x = n.x ?? 0;
				const y = n.y ?? 0;

				// Node circle
				ctx.beginPath();
				ctx.arc(x, y, size, 0, 2 * Math.PI);
				ctx.fillStyle = color;
				ctx.fill();

				// PC gold ring
				if (nd.is_player_character) {
					ctx.strokeStyle = '#b89f6a';
					ctx.lineWidth = 2;
					ctx.stroke();
				}

				// Label
				const fontSize = Math.max(10 / globalScale, 3);
				ctx.font = `${fontSize}px 'DM Sans', sans-serif`;
				ctx.textAlign = 'center';
				ctx.textBaseline = 'top';
				ctx.fillStyle = '#5c5549';
				ctx.fillText(nd.name, x, y + size + 2);
			})
			.nodePointerAreaPaint((n: ForceNode, color: string, ctx: CanvasRenderingContext2D) => {
				const size = nodeSize(n.nodeData);
				ctx.beginPath();
				ctx.arc(n.x ?? 0, n.y ?? 0, size + 2, 0, 2 * Math.PI);
				ctx.fillStyle = color;
				ctx.fill();
			})
			.linkColor((link: ForceLink) => trustColor(link.edgeData.trust_score))
			.linkWidth((link: ForceLink) => Math.max(0.5, Math.abs(link.edgeData.trust_score) / 50 * 3))
			.linkLineDash((link: ForceLink) => link.edgeData.trend === 'falling' ? [4, 4] : [])
			.linkDirectionalArrowLength(0)
			.backgroundColor('transparent')
			.cooldownTicks(100)
			.onNodeClick((n: ForceNode) => {
				if (onNodeClick) onNodeClick(n.nodeData);
			});

		// Responsive
		resizeObserver = new ResizeObserver(() => {
			if (graph && container) {
				graph.width(container.clientWidth);
				graph.height(container.clientHeight);
			}
		});
		resizeObserver.observe(container);
	}

	$effect(() => {
		if (graph && data) {
			const { nodes, links } = buildGraphData(data);
			graph.graphData({ nodes, links });
		}
	});

	onMount(() => {
		initGraph();
	});

	onDestroy(() => {
		resizeObserver?.disconnect();
		if (graph) {
			graph._destructor?.();
			graph = null;
		}
	});
</script>

<div bind:this={container} class="w-full h-full"></div>
