<div class="max-w-4xl mx-auto space-y-4">
	<div>
		<h1 class="text-2xl font-bold text-text">Dashboard</h1>
		<p class="text-text-dim text-sm mt-1">Entity graph, card library, and orphan detection.</p>
	</div>
	<div class="bg-surface border border-border-custom rounded-lg p-6 space-y-3 text-sm text-text-dim">
		<p>This page is planned but not yet built. See <code class="font-mono text-xs">.claude/plans/ui/rp-dashboard.md</code> for the full spec.</p>
		<p>What's needed before building:</p>
		<ul class="list-disc list-inside space-y-1 text-xs font-mono">
			<li>GET /api/cards/connections — bulk entity connections (for graph)</li>
			<li>connection_count added to GET /api/cards list response</li>
		</ul>
		<p>What can be built now: card library, detail panel, orphan/gap audit tab.</p>
	</div>
</div>
