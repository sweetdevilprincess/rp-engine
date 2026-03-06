<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import type { GraphData, GraphNode, GraphEdge } from '$lib/types';
	import { cardTypeHex, EDGE_TYPE_COLORS } from '$lib/utils/colors';

	interface Props {
		data: GraphData;
		filter?: string;
		onNodeClick?: ((node: GraphNode) => void) | null;
	}

	let { data, filter = '', onNodeClick = null }: Props = $props();

	let container: HTMLDivElement;
	let graph: any = null;

	interface ForceNode {
		id: string;
		card_type: string;
		importance: string;
		connections: number;
		x?: number;
		y?: number;
	}
	interface ForceLink {
		source: string;
		target: string;
		connection_type: string;
		weight: number;
	}

	function buildGraphData(data: GraphData, filter: string) {
		const q = filter.toLowerCase().trim();
		let nodes = data.nodes;
		let edges = data.edges;

		if (q) {
			const matchedNames = new Set(
				nodes.filter(n => n.name.toLowerCase().includes(q) || n.card_type.toLowerCase().includes(q))
					.map(n => n.name)
			);
			// Also include nodes connected to matched nodes
			edges.forEach(e => {
				if (matchedNames.has(e.from)) matchedNames.add(e.to);
				if (matchedNames.has(e.to)) matchedNames.add(e.from);
			});
			nodes = nodes.filter(n => matchedNames.has(n.name));
			const nameSet = new Set(nodes.map(n => n.name));
			edges = edges.filter(e => nameSet.has(e.from) && nameSet.has(e.to));
		}

		// Count connections per node for sizing
		const connCounts: Record<string, number> = {};
		edges.forEach(e => {
			connCounts[e.from] = (connCounts[e.from] || 0) + 1;
			connCounts[e.to] = (connCounts[e.to] || 0) + 1;
		});

		// Compute edge weights: count parallel edges between same node pair
		const pairCounts: Record<string, number> = {};
		edges.forEach(e => {
			const key = [e.from, e.to].sort().join('::');
			pairCounts[key] = (pairCounts[key] || 0) + 1;
		});

		// Build importance lookup for weight boosting
		const importanceRank: Record<string, number> = {};
		nodes.forEach(n => {
			const ranks: Record<string, number> = {
				critical: 4, pov: 3, love_interest: 3, antagonist: 3,
				main: 2, primary: 2, recurring: 1, secondary: 1,
			};
			importanceRank[n.name] = ranks[n.importance] ?? 0;
		});

		const forceNodes: ForceNode[] = nodes.map(n => ({
			id: n.name,
			card_type: n.card_type,
			importance: n.importance,
			connections: connCounts[n.name] || 0,
		}));

		const forceLinks: ForceLink[] = edges.map(e => {
			const pairKey = [e.from, e.to].sort().join('::');
			const parallelCount = pairCounts[pairKey] || 1;
			const importanceBoost = Math.max(importanceRank[e.from] || 0, importanceRank[e.to] || 0);
			return {
				source: e.from,
				target: e.to,
				connection_type: e.connection_type,
				weight: parallelCount + importanceBoost * 0.5,
			};
		});

		return { nodes: forceNodes, links: forceLinks };
	}

	function getNodeColor(node: ForceNode): string {
		return cardTypeHex(node.card_type);
	}

	function getEdgeColor(link: ForceLink): string {
		const type = link.connection_type.toLowerCase();
		for (const [key, color] of Object.entries(EDGE_TYPE_COLORS)) {
			if (type.includes(key)) return color;
		}
		return '#475569';
	}

	function getNodeRadius(node: ForceNode): number {
		// Base size by importance, scaled up by connections — capped to prevent huge nodes
		const importanceBase: Record<string, number> = {
			critical: 6, pov: 5.5, love_interest: 5.5, antagonist: 5.5,
			main: 5, primary: 5, recurring: 4.5, secondary: 4.5,
			supporting: 4, important: 4, minor: 3, background: 2.5,
		};
		const base = importanceBase[node.importance] || 3;
		return Math.min(base + Math.min(node.connections * 0.3, 3), 9);
	}

	function getLinkWidth(link: ForceLink): number {
		// Base width from connection type
		const type = link.connection_type.toLowerCase();
		let base = 1;
		if (type.includes('relationship') || type.includes('family') || type.includes('love')) base = 1.5;
		if (type.includes('member') || type.includes('belongs')) base = 1.2;
		// Scale by computed weight (parallel edges + importance)
		return base * Math.min(link.weight, 4);
	}

	async function initGraph() {
		if (!container) return;
		// force-graph exports a Kapsule factory (called as ForceGraph()(element))
		// but its .d.ts declares a class. Cast to any to match runtime behavior.
		const ForceGraph = (await import('force-graph')).default as any;

		const gd = buildGraphData(data, filter);
		const rect = container.getBoundingClientRect();

		graph = ForceGraph()(container)
			.width(rect.width)
			.height(rect.height)
			.backgroundColor('transparent')
			.nodeId('id')
			.nodeLabel((node: ForceNode) => `${node.id} (${node.card_type})`)
			.nodeCanvasObject((node: ForceNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
				const r = getNodeRadius(node);
				const color = getNodeColor(node);

				// Glow for highly connected nodes
				if (node.connections >= 4) {
					ctx.shadowColor = color;
					ctx.shadowBlur = 8;
				}

				// Circle
				ctx.beginPath();
				ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
				ctx.fillStyle = color;
				ctx.fill();
				ctx.shadowBlur = 0;

				// Border
				ctx.strokeStyle = 'rgba(56,50,43,0.15)';
				ctx.lineWidth = 0.5;
				ctx.stroke();

				// Label when zoomed in enough
				if (globalScale > 1.2) {
					ctx.font = `${Math.max(10 / globalScale, 2)}px sans-serif`;
					ctx.textAlign = 'center';
					ctx.textBaseline = 'top';
					ctx.fillStyle = 'rgba(56,50,43,0.85)';
					ctx.fillText(node.id, node.x!, node.y! + r + 2);
				}
			})
			.nodePointerAreaPaint((node: ForceNode, color: string, ctx: CanvasRenderingContext2D) => {
				const r = getNodeRadius(node);
				ctx.beginPath();
				ctx.arc(node.x!, node.y!, r + 2, 0, 2 * Math.PI);
				ctx.fillStyle = color;
				ctx.fill();
			})
			.linkColor((link: ForceLink) => {
				const baseColor = getEdgeColor(link);
				// Higher weight = more opaque
				const opacity = Math.min(0.3 + link.weight * 0.15, 1);
				return baseColor + Math.round(opacity * 255).toString(16).padStart(2, '0');
			})
			.linkWidth((link: ForceLink) => getLinkWidth(link))
			.linkLabel((link: ForceLink) => link.connection_type)
			.linkDirectionalArrowLength(3)
			.linkDirectionalArrowRelPos(1)
			.enableNodeDrag(true)
			.minZoom(0.3)
			.maxZoom(8)
			.cooldownTime(3000)
			.onNodeClick((node: ForceNode) => {
				if (onNodeClick) onNodeClick({ name: node.id, card_type: node.card_type, importance: node.importance });
			})
			.graphData(gd);

		// Fit view after simulation stabilizes
		setTimeout(() => {
			if (graph) graph.zoomToFit(400, 40);
		}, 1500);
	}

	// Update graph data when filter or data changes
	$effect(() => {
		if (graph && data) {
			const gd = buildGraphData(data, filter);
			graph.graphData(gd);
			setTimeout(() => {
				if (graph) graph.zoomToFit(400, 40);
			}, 1500);
		}
	});

	onMount(() => {
		initGraph();
	});

	onDestroy(() => {
		if (graph) {
			graph._destructor();
			graph = null;
		}
	});

	function handleResize() {
		if (!graph || !container) return;
		const rect = container.getBoundingClientRect();
		graph.width(rect.width).height(rect.height);
	}
</script>

<svelte:window onresize={handleResize} />

<div
	bind:this={container}
	class="w-full h-full rounded-lg overflow-hidden"
	style="min-height: 500px"
></div>
