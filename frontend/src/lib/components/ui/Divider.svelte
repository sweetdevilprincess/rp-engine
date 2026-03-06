<!--
  Ornamental gold divider with center dot.
  Usage: <Divider />
-->
<div class="divider">
	<div class="line"></div>
	<div class="dot"></div>
	<div class="line"></div>
</div>

<style>
	.divider {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 4px 0;
	}
	.line {
		flex: 1;
		height: 1px;
		background: linear-gradient(90deg, transparent, var(--color-gold-border), transparent);
	}
	.dot {
		width: 4px;
		height: 4px;
		border-radius: 50%;
		background: var(--color-gold-border);
	}
</style>
