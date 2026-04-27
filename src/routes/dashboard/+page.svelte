<script lang="ts">
	import { onMount } from 'svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import { Badge } from '$lib/components/ui/badge';
	import SourceBadge from '$lib/components/SourceBadge.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import UserMenu from '$lib/components/UserMenu.svelte';
	import * as Table from '$lib/components/ui/table';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { formatShortDate } from '$lib/date-utils';
	import MapIcon from '@lucide/svelte/icons/map';
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import ArrowDownIcon from '@lucide/svelte/icons/arrow-down';
	import MinusIcon from '@lucide/svelte/icons/minus';
	import SearchIcon from '@lucide/svelte/icons/search';
	import ArchiveIcon from '@lucide/svelte/icons/archive';
	import type { DashboardFeature } from '../api/dashboard/+server';

	type SortKey = keyof DashboardFeature | 'change';

	let features: DashboardFeature[] = $state([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let searchQuery = $state('');
	let sortKey = $state<SortKey>('name');
	let sortDirection = $state<'asc' | 'desc'>('asc');
	let unit = $state<'C' | 'F'>('C');

	function convertTemp(kelvin: number | null): string {
		if (kelvin == null) return '--';
		if (unit === 'C') return (kelvin - 273.15).toFixed(1);
		return ((kelvin - 273.15) * 9 / 5 + 32).toFixed(1);
	}

	function tempDelta(current: number | null, previous: number | null): number | null {
		if (current == null || previous == null) return null;
		if (unit === 'C') return current - previous;
		return (current - previous) * 9 / 5;
	}

	function formatDelta(delta: number | null): string {
		if (delta == null) return '';
		const abs = Math.abs(delta);
		const sign = delta > 0 ? '+' : delta < 0 ? '-' : '';
		if (unit === 'C') return `${sign}${abs.toFixed(1)}`;
		return `${sign}${abs.toFixed(1)}`;
	}

	const unitSymbol = $derived(unit === 'C' ? '\u00B0C' : '\u00B0F');

	function sortValue(f: DashboardFeature, key: SortKey): string | number | null {
		if (key === 'change') {
			if (f.latest_mean_temp == null || f.prev_mean_temp == null) return null;
			return f.latest_mean_temp - f.prev_mean_temp;
		}
		const v = f[key];
		if (Array.isArray(v)) return null;
		return v;
	}

	const filteredFeatures = $derived.by(() => {
		let result = features;
		if (searchQuery.trim()) {
			const q = searchQuery.trim().toLowerCase();
			result = result.filter(
				(f) =>
					f.name.toLowerCase().includes(q) ||
					f.location.toLowerCase().includes(q) ||
					f.feature_id.toLowerCase().includes(q)
			);
		}
		return result.toSorted((a, b) => {
			const aVal = sortValue(a, sortKey);
			const bVal = sortValue(b, sortKey);
			if (aVal == null && bVal == null) return 0;
			if (aVal == null) return 1;
			if (bVal == null) return -1;
			let cmp: number;
			if (typeof aVal === 'string' && typeof bVal === 'string') {
				cmp = aVal.localeCompare(bVal);
			} else {
				cmp = (aVal as number) - (bVal as number);
			}
			return sortDirection === 'asc' ? cmp : -cmp;
		});
	});

	function toggleSort(key: SortKey) {
		if (sortKey === key) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortDirection = key === 'name' ? 'asc' : 'desc';
		}
	}

	const totalFeatures = $derived(features.length);
	const staleCount = $derived(
		features.filter((f) => f.days_since_observation != null && f.days_since_observation > 14).length
	);

	function freshnessColor(days: number | null): string {
		if (days == null) return 'text-muted-foreground';
		if (days <= 3) return 'text-green-600 dark:text-green-400';
		if (days <= 14) return 'text-yellow-600 dark:text-yellow-400';
		return 'text-red-600 dark:text-red-400';
	}

	function freshnessLabel(days: number | null): string {
		if (days == null) return 'No data';
		if (days === 0) return 'Today';
		if (days === 1) return '1 day ago';
		return `${days}d ago`;
	}

	async function load() {
		loading = true;
		error = null;
		try {
			const res = await fetch('/api/dashboard');
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			features = data.features || [];
		} catch (err) {
			console.error('Error loading dashboard:', err);
			error = "Couldn't load dashboard.";
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<svelte:head>
	<title>Dashboard - Satellite Water Temps</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<header class="border-b bg-card">
		<div class="container mx-auto px-6 py-4 flex justify-between items-center max-w-7xl">
			<span class="font-semibold text-foreground">Dashboard</span>
			<div class="flex items-center gap-3">
				<div class="flex items-center gap-1 rounded-lg border p-1 bg-muted/50">
					<button
						class="px-2 py-0.5 text-sm rounded-md transition-colors {unit === 'C'
							? 'bg-background shadow-sm font-medium'
							: 'text-muted-foreground hover:text-foreground'}"
						onclick={() => (unit = 'C')}
					>
						&deg;C
					</button>
					<button
						class="px-2 py-0.5 text-sm rounded-md transition-colors {unit === 'F'
							? 'bg-background shadow-sm font-medium'
							: 'text-muted-foreground hover:text-foreground'}"
						onclick={() => (unit = 'F')}
					>
						&deg;F
					</button>
				</div>
				<UserMenu inline />
			</div>
		</div>
	</header>

	<div class="w-[95%] mx-auto py-5">
		{#if error}
			<div class="mb-4 flex items-center justify-between rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm">
				<span class="text-destructive">{error}</span>
				<Button variant="outline" size="sm" onclick={load}>Retry</Button>
			</div>
		{/if}

		<!-- Search + meta -->
		<div class="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
			<div class="relative max-w-sm flex-1 min-w-[200px]">
				<SearchIcon class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
				<Input
					placeholder="Filter water bodies..."
					class="pl-9"
					bind:value={searchQuery}
				/>
			</div>
			{#if !loading}
				<div class="text-xs text-muted-foreground tabular-nums">
					Showing {filteredFeatures.length} of {totalFeatures}
					{#if staleCount > 0}
						&middot; <span class="text-red-600 dark:text-red-400">{staleCount} stale (&gt;14d)</span>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Table -->
		{#if loading}
			<div class="border rounded-lg">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>Name</Table.Head>
							<Table.Head>Type</Table.Head>
							<Table.Head class="text-right">Mean Temp</Table.Head>
							<Table.Head>Trend <span class="text-muted-foreground font-normal">(last 10)</span></Table.Head>
							<Table.Head class="text-right">Change</Table.Head>
							<Table.Head class="text-right">Range</Table.Head>
							<Table.Head>Source</Table.Head>
							<Table.Head class="text-right">Obs</Table.Head>
							<Table.Head class="text-right">Freshness</Table.Head>
							<Table.Head class="w-20"></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each Array(15) as _}
							<Table.Row>
								<Table.Cell><Skeleton class="h-4 w-28" /></Table.Cell>
								<Table.Cell><Skeleton class="h-5 w-12 rounded-full" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-14 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-[20px] w-20" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-14 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-20 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-5 w-20 rounded-full" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-8 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-14 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-12" /></Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{:else if filteredFeatures.length === 0}
			<div class="border rounded-lg py-16 text-center text-muted-foreground">
				{#if searchQuery.trim()}
					No water bodies match "{searchQuery}"
				{:else}
					No water bodies found
				{/if}
			</div>
		{:else}
			<div class="border rounded-lg overflow-x-auto">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							{#each [
								{ key: 'name' as SortKey, label: 'Name', align: '', sortable: true },
								{ key: 'location' as SortKey, label: 'Type', align: '', sortable: true },
								{ key: 'latest_mean_temp' as SortKey, label: 'Mean Temp', align: 'text-right', sortable: true },
								{ key: null, label: 'Trend', sublabel: 'last 10', align: '', sortable: false },
								{ key: 'change' as SortKey, label: 'Change', align: 'text-right', sortable: true },
								{ key: 'latest_min_temp' as SortKey, label: 'Range', align: 'text-right', sortable: true },
								{ key: 'latest_source' as SortKey, label: 'Source', align: '', sortable: true },
								{ key: 'observation_count' as SortKey, label: 'Obs', align: 'text-right', sortable: true },
								{ key: 'days_since_observation' as SortKey, label: 'Freshness', align: 'text-right', sortable: true },
							] as col}
								<Table.Head class="{col.align} select-none">
									{#if col.sortable && col.key}
										{@const active = sortKey === col.key}
										<button
											class="inline-flex items-center gap-1 hover:text-foreground transition-colors"
											onclick={() => toggleSort(col.key!)}
										>
											{col.label}
											<span
												class="text-xs w-3 inline-block text-muted-foreground"
												aria-hidden="true"
											>
												{active ? (sortDirection === 'asc' ? '\u2191' : '\u2193') : ''}
											</span>
										</button>
									{:else}
										<span class="inline-flex items-center gap-1">
											{col.label}
											{#if col.sublabel}
												<span class="text-muted-foreground font-normal">({col.sublabel})</span>
											{/if}
										</span>
									{/if}
								</Table.Head>
							{/each}
							<Table.Head class="w-20"></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each filteredFeatures as feature (feature.feature_id)}
							{@const delta = tempDelta(feature.latest_mean_temp, feature.prev_mean_temp)}
							<Table.Row>
								<Table.Cell>
									<a
										href="/feature/{encodeURIComponent(feature.feature_id)}"
										class="font-medium hover:underline"
									>
										{feature.name}
									</a>
								</Table.Cell>
								<Table.Cell>
									<Badge variant="outline" class="text-xs capitalize">
										{feature.location}
									</Badge>
								</Table.Cell>
								<Table.Cell class="text-right tabular-nums font-medium">
									{convertTemp(feature.latest_mean_temp)}{feature.latest_mean_temp != null ? unitSymbol : ''}
								</Table.Cell>
								<Table.Cell>
									<Sparkline values={feature.recent_means} />
								</Table.Cell>
								<Table.Cell class="text-right">
									{#if delta != null}
										<span class="inline-flex items-center gap-0.5 tabular-nums text-sm {delta > 0.5 ? 'text-red-600 dark:text-red-400' : delta < -0.5 ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'}">
											{#if delta > 0.5}
												<ArrowUpIcon class="size-3" />
											{:else if delta < -0.5}
												<ArrowDownIcon class="size-3" />
											{:else}
												<MinusIcon class="size-3" />
											{/if}
											{formatDelta(delta)}
										</span>
									{:else}
										<span class="text-muted-foreground">--</span>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-right tabular-nums text-sm text-muted-foreground">
									{#if feature.latest_min_temp != null && feature.latest_max_temp != null}
										{convertTemp(feature.latest_min_temp)} – {convertTemp(feature.latest_max_temp)}
									{:else}
										--
									{/if}
								</Table.Cell>
								<Table.Cell>
									{#if feature.latest_source}
										<SourceBadge source={feature.latest_source} />
									{:else}
										<span class="text-muted-foreground">--</span>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-right tabular-nums">
									{feature.observation_count}
								</Table.Cell>
								<Table.Cell class="text-right">
									<Tooltip.Provider>
										<Tooltip.Root>
											<Tooltip.Trigger>
												{#snippet child({ props })}
													<span {...props} class="tabular-nums text-sm {freshnessColor(feature.days_since_observation)}">
														{freshnessLabel(feature.days_since_observation)}
													</span>
												{/snippet}
											</Tooltip.Trigger>
											<Tooltip.Content>
												{#if feature.latest_date}
													{formatShortDate(feature.latest_date)}
												{:else}
													No observations
												{/if}
											</Tooltip.Content>
										</Tooltip.Root>
									</Tooltip.Provider>
								</Table.Cell>
								<Table.Cell>
									<div class="flex items-center gap-1">
										<Tooltip.Provider>
											<Tooltip.Root>
												<Tooltip.Trigger>
													{#snippet child({ props })}
														<a
															{...props}
															href="/feature/{encodeURIComponent(feature.feature_id)}"
															class="text-muted-foreground hover:text-foreground transition-colors p-1"
														>
															<MapIcon class="size-3.5" />
														</a>
													{/snippet}
												</Tooltip.Trigger>
												<Tooltip.Content>View on map</Tooltip.Content>
											</Tooltip.Root>
										</Tooltip.Provider>
										<Tooltip.Provider>
											<Tooltip.Root>
												<Tooltip.Trigger>
													{#snippet child({ props })}
														<a
															{...props}
															href="/archive/{encodeURIComponent(feature.feature_id)}"
															class="text-muted-foreground hover:text-foreground transition-colors p-1"
														>
															<ArchiveIcon class="size-3.5" />
														</a>
													{/snippet}
												</Tooltip.Trigger>
												<Tooltip.Content>View archive</Tooltip.Content>
											</Tooltip.Root>
										</Tooltip.Provider>
									</div>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{/if}
	</div>
</div>
