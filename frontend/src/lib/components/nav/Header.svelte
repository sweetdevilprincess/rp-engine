<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { activeRP } from '$lib/stores/rp';
	import { serverHealth } from '$lib/stores/health';
	import BranchIndicator from './BranchIndicator.svelte';

	/** Bound from layout - true when main content has scrolled past threshold */
	interface Props {
		scrolled?: boolean;
	}

	let { scrolled = false }: Props = $props();

	const navLinks = [
		{ path: '/',            label: 'Home',        rpRequired: false },
		{ path: '/cards',       label: 'Cards',       rpRequired: true  },
		{ path: '/sessions',    label: 'Sessions',    rpRequired: true  },
		{ path: '/generations', label: 'Generations', rpRequired: true  },
		{ path: '/dashboard',   label: 'Dashboard',   rpRequired: true  },
		{ path: '/chat',        label: 'Chat',        rpRequired: true  },
		{ path: '/dev',         label: 'Dev',         rpRequired: true  },
		{ path: '/settings',    label: 'Settings',    rpRequired: false },
	];

	function getHref(link: (typeof navLinks)[0]): string {
		if (!link.rpRequired) return link.path;
		if (!$activeRP) return '#';
		return `/${$activeRP.rp_folder}${link.path}`;
	}

	function isActive(link: (typeof navLinks)[0]): boolean {
		if (link.path === '/') return $page.url.pathname === '/';
		if (!link.rpRequired) return $page.url.pathname === link.path;
		if (!$activeRP) return false;
		return $page.url.pathname.startsWith(`/${$activeRP.rp_folder}${link.path}`);
	}

	function isDisabled(link: (typeof navLinks)[0]): boolean {
		return link.rpRequired && !$activeRP;
	}

	let initials = $derived(
		$activeRP
			? $activeRP.rp_folder.split(/[-_]/).map((w: string) => w[0]?.toUpperCase()).join('').slice(0, 2)
			: 'RP'
	);
</script>

<div class="header-wrap" class:scrolled>
	<header class="header" class:header-scrolled={scrolled}>
		<!-- RP Avatar -->
		<div class="avatar-container" class:avatar-scrolled={scrolled}>
			<button
				class="avatar"
				class:avatar-sm={scrolled}
				onclick={() => $activeRP ? goto(`/${$activeRP.rp_folder}/`) : goto('/')}
				title={$activeRP ? $activeRP.rp_folder : 'Home'}
			>
				<span class="avatar-text" class:avatar-text-sm={scrolled}>
					{initials}
				</span>
			</button>
		</div>

		<!-- Nav links - horizontal scrollable -->
		<nav class="nav-scroll" class:nav-scrolled={scrolled}>
			{#each navLinks as link}
				{#if isDisabled(link)}
					<span class="nav-link nav-link-disabled">{link.label}</span>
				{:else}
					<a
						href={getHref(link)}
						class="nav-link"
						class:nav-link-active={isActive(link)}
					>
						{link.label}
					</a>
				{/if}
			{/each}
		</nav>

		<!-- Right side -->
		<div class="right-group" class:right-scrolled={scrolled}>
			{#if $activeRP}
				<button
					class="rp-name font-serif"
					onclick={() => goto(`/${$activeRP!.rp_folder}/`)}
					title="Go to RP overview"
				>
					{$activeRP.rp_folder}
				</button>
				<BranchIndicator />
			{/if}
			<span
				class="status-dot"
				class:status-online={$serverHealth.status === 'online'}
				class:status-offline={$serverHealth.status !== 'online'}
				title="Server {$serverHealth.status}"
			></span>
		</div>
	</header>

	<!-- Decorative gold line -->
	{#if !scrolled}
		<div class="gold-line"></div>
	{/if}
</div>

<style>
	.header-wrap {
		position: relative;
		flex-shrink: 0;
		z-index: 40;
	}

	.header {
		height: 76px;
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-border-custom);
		display: flex;
		align-items: flex-end;
		padding: 0 16px 10px 16px;
		gap: 12px;
		transition: height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
		            padding 0.35s cubic-bezier(0.4, 0, 0.2, 1),
		            align-items 0.35s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.header-scrolled {
		height: 52px;
		align-items: center;
		padding: 0 16px;
	}

	/* -- Avatar -- */
	.avatar-container {
		position: relative;
		flex-shrink: 0;
		z-index: 2;
		margin-bottom: -12px;
		align-self: flex-end;
		transition: margin 0.35s cubic-bezier(0.4, 0, 0.2, 1),
		            align-self 0.35s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.avatar-scrolled {
		margin-bottom: 0;
		align-self: center;
	}

	.avatar {
		width: 52px;
		height: 52px;
		border-radius: 50%;
		border: 2.5px solid var(--color-warm);
		background: linear-gradient(135deg, var(--color-warm-soft), var(--color-gold-soft));
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		overflow: hidden;
		box-shadow: 0 3px 12px rgba(184, 159, 106, 0.2), 0 0 0 3px var(--color-surface);
		transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
		            height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
		            box-shadow 0.35s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.avatar-sm {
		width: 32px;
		height: 32px;
		box-shadow: none;
	}

	.avatar-text {
		font-family: 'Lora', Georgia, serif;
		font-weight: 700;
		font-size: 17px;
		color: var(--color-warm-deep);
		transition: font-size 0.35s cubic-bezier(0.4, 0, 0.2, 1);
	}
	.avatar-text-sm {
		font-size: 11px;
	}

	/* -- Nav -- */
	.nav-scroll {
		display: flex;
		gap: 3px;
		flex: 1;
		align-items: center;
		align-self: flex-end;
		padding-bottom: 2px;
		overflow-x: auto;
		overflow-y: hidden;
		scrollbar-width: none;          /* Firefox */
		-ms-overflow-style: none;       /* IE/Edge */
		transition: align-self 0.3s ease, padding 0.3s ease;
	}
	.nav-scroll::-webkit-scrollbar { display: none; }
	.nav-scrolled {
		align-self: center;
		padding-bottom: 0;
	}

	.nav-link {
		padding: 5px 14px;
		border-radius: 99px;
		font-size: 13px;
		font-weight: 400;
		border: 1px solid transparent;
		background: transparent;
		color: var(--color-text-dim);
		text-decoration: none;
		white-space: nowrap;
		transition: all 0.15s ease;
		flex-shrink: 0;
	}
	.nav-link:hover {
		color: var(--color-text);
	}
	.nav-link-active {
		font-weight: 600;
		border-color: var(--color-accent-border);
		background: var(--color-accent-soft);
		color: var(--color-accent);
	}
	.nav-link-disabled {
		color: var(--color-text-muted);
		cursor: not-allowed;
		opacity: 0.4;
	}

	/* -- Right side -- */
	.right-group {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
		align-self: flex-end;
		padding-bottom: 2px;
		transition: align-self 0.3s ease, padding 0.3s ease;
	}
	.right-scrolled {
		align-self: center;
		padding-bottom: 0;
	}

	.rp-name {
		font-size: 12px;
		color: var(--color-text-dim);
		font-style: italic;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		transition: color 0.15s;
	}
	.rp-name:hover { color: var(--color-text); }

	.status-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.status-online { background: var(--color-success); }
	.status-offline { background: var(--color-error); }

	/* -- Gold decorative line -- */
	.gold-line {
		height: 2px;
		background: linear-gradient(
			90deg,
			transparent 5%,
			var(--color-gold-border) 25%,
			color-mix(in srgb, var(--color-gold) 53%, transparent) 50%,
			var(--color-gold-border) 75%,
			transparent 95%
		);
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
	}
</style>
