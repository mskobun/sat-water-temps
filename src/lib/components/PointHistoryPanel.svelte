<script lang="ts">
	import { parseDate } from '$lib/date-utils';
	import * as Chart from '$lib/components/ui/chart';
	import { LineChart } from 'layerchart';
	import { scaleUtc } from 'd3-scale';
	import { curveNatural } from 'd3-shape';
	import { Button } from '$lib/components/ui/button';
	import { Spinner } from '$lib/components/ui/spinner';
	import XIcon from '@lucide/svelte/icons/x';
	import type { DeckTemperatureOverlay } from '$lib/deck-temperature-overlay';
	import type { PointHistoryEntry } from '$lib/duckdb-cache';
	import { fetchTemperatureMetadata } from '$lib/api';

	type DuckDBCacheModule = typeof import('$lib/duckdb-cache');

	let {
		selectedPoint = null,
		featureId = null,
		dataSource = '',
		selectedDate = '',
		unit = 'Celsius',
		title = 'Point history',
		deckOverlay = null,
		halfPixelX = 0,
		halfPixelY = 0,
		pixelTolerance = 0.01,
		getDuckDBCacheModule,
		onclose,
		ondatechange
	}: {
		selectedPoint?: { longitude: number; latitude: number } | null;
		featureId?: string | null;
		dataSource?: string;
		selectedDate?: string;
		unit?: 'Kelvin' | 'Celsius' | 'Fahrenheit';
		title?: string;
		deckOverlay?: DeckTemperatureOverlay | null;
		halfPixelX?: number;
		halfPixelY?: number;
		pixelTolerance?: number;
		getDuckDBCacheModule: () => Promise<DuckDBCacheModule | null>;
		onclose?: () => void;
		ondatechange?: (date: string) => void;
	} = $props();

	// --- Internal state ---
	let entries: PointHistoryEntry[] = $state([]);
	let loading = $state(false);

	// --- Reactively load history when selectedPoint changes ---
	let prevPointKey = '';
	$effect(() => {
		const key = selectedPoint ? `${featureId}:${selectedPoint.longitude}:${selectedPoint.latitude}` : '';
		if (key === prevPointKey) return;
		prevPointKey = key;

		if (!selectedPoint || !featureId) {
			entries = [];
			loading = false;
			return;
		}

		void loadHistory(featureId, selectedPoint.longitude, selectedPoint.latitude);
	});

	// Reload when dataSource changes (same point, different source)
	let prevDataSource = '';
	$effect(() => {
		if (dataSource === prevDataSource) return;
		prevDataSource = dataSource;
		if (selectedPoint && featureId) {
			void loadHistory(featureId, selectedPoint.longitude, selectedPoint.latitude);
		}
	});

	// Clear highlight when component unmounts or point clears
	$effect(() => {
		return () => {
			deckOverlay?.setHighlight(null);
		};
	});

	async function loadHistory(fid: string, longitude: number, latitude: number) {
		loading = true;
		try {
			const source = (dataSource === 'landsat' ? 'landsat' : 'ecostress') as 'ecostress' | 'landsat';
			const duckdbCache = await getDuckDBCacheModule();
			if (!duckdbCache) return;
			const feature = await duckdbCache.fetchDuckDBFeature(fid, source);
			if (!feature) {
				entries = [];
				return;
			}
			entries = await duckdbCache.getPointHistory(feature, longitude, latitude, pixelTolerance, source);
		} catch (err) {
			console.error('Error loading point history:', err);
			entries = [];
		} finally {
			loading = false;
		}
	}

	// --- Hover highlight ---
	function handleRowHover(entry: PointHistoryEntry | null) {
		if (!deckOverlay) return;
		if (!entry) {
			deckOverlay.setHighlight(null);
			return;
		}

		// Landsat: fetch that date's transform for exact quad
		if (entry.row != null && entry.col != null && featureId) {
			const { row, col, date } = entry;
			fetchTemperatureMetadata(featureId, date).then((meta) => {
				if (!meta?.sourceCrs || !meta.transform) return;
				import('$lib/landsat-pixel-quads').then(({ pixelQuadWgs84 }) => {
					deckOverlay?.setHighlight(pixelQuadWgs84(row, col, meta.sourceCrs!, meta.transform!));
				});
			});
			return;
		}

		// ECOSTRESS or fallback: rectangle from pixel center
		const { longitude: lng, latitude: lat } = entry;
		deckOverlay.setHighlight([
			[lng - halfPixelX, lat - halfPixelY],
			[lng + halfPixelX, lat - halfPixelY],
			[lng + halfPixelX, lat + halfPixelY],
			[lng - halfPixelX, lat + halfPixelY]
		]);
	}

	// --- Display helpers ---
	function convertTemp(k: number): number {
		if (unit === 'Celsius') return k - 273.15;
		if (unit === 'Fahrenheit') return (k - 273.15) * 9 / 5 + 32;
		return k;
	}

	let unitSymbol = $derived(unit === 'Kelvin' ? 'K' : unit === 'Celsius' ? '°C' : '°F');

	function formatCoordinate(v: number): string {
		return v.toFixed(4);
	}

	function formatDistance(deg: number): string {
		const m = deg * 111_000;
		return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
	}

	function fmtTableDate(dateStr: string): string {
		return parseDate(dateStr).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: '2-digit'
		});
	}

	let rows = $derived(
		entries.map((e) => ({ ...e, displayTemperature: convertTemp(e.temperature) }))
	);

	let chartData = $derived(
		[...rows]
			.reverse()
			.map((r) => ({ date: parseDate(r.date), temperature: r.displayTemperature }))
	);

	const chartConfig = {
		temperature: { label: 'Temperature', color: 'var(--chart-1)' }
	} satisfies Chart.ChartConfig;

	let sourceLabel = $derived.by(() => {
		const src = rows[0]?.source;
		if (src === 'landsat') return 'Landsat';
		return 'ECOSTRESS';
	});

	let displayTitle = $derived(rows.length > 0 ? `${title} (${sourceLabel})` : title);
</script>

<div class="rounded-lg border bg-background shadow-lg p-3 flex flex-col gap-2.5 min-w-[320px] max-w-[380px]">
	<!-- Header -->
	<div class="flex items-center justify-between gap-2">
		<h3 class="text-sm font-semibold">{displayTitle}</h3>
		<Button variant="ghost" size="icon-sm" onclick={() => onclose?.()}>
			<XIcon class="size-4" />
			<span class="sr-only">Close</span>
		</Button>
	</div>

	{#if !selectedPoint}
		<p class="text-xs text-muted-foreground">Click a temperature pixel to see its history.</p>

	{:else if loading}
		<div class="flex items-center justify-center gap-2 py-6">
			<Spinner class="size-4 text-muted-foreground" />
			<p class="text-xs text-muted-foreground">Querying…</p>
		</div>

	{:else}
		<!-- Coords + count -->
		<div class="flex items-center justify-between text-xs text-muted-foreground">
			<span class="tabular-nums">
				{formatCoordinate(selectedPoint.latitude)}°,&nbsp;{formatCoordinate(selectedPoint.longitude)}°
			</span>
			<span>{rows.length} observation{rows.length === 1 ? '' : 's'}</span>
		</div>

		<!-- Chart -->
		{#if chartData.length > 1}
			<div class="rounded-md border bg-muted/10 px-1 pb-1">
				<Chart.Container config={chartConfig} class="h-44 w-full">
					<LineChart
						data={chartData}
						x="date"
						xScale={scaleUtc()}
						axis="x"
						padding={{ top: 12, left: 24, bottom: 20, right: 24 }}
						points={{ r: 4 }}
							series={[{ key: 'temperature', label: 'Temperature', color: chartConfig.temperature.color }]}
							props={{
								spline: { curve: curveNatural, strokeWidth: 2 },
								highlight: { points: { r: 6 } },
								xAxis: {
									format: (d: Date) =>
										d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
								}
							}}
						>
							{#snippet tooltip()}
							<Chart.Tooltip
								indicator="dot"
									labelFormatter={(v) => {
										if (!(v instanceof Date)) return String(v);
										const date = v.toLocaleDateString('en-GB', {
											day: 'numeric',
											month: 'short',
											year: 'numeric'
										});
										// Show time for ECOSTRESS (non-midnight observations)
										if (v.getHours() !== 0 || v.getMinutes() !== 0) {
											const time = v.toLocaleTimeString('en-GB', {
												hour: '2-digit',
												minute: '2-digit'
											});
											return `${date}, ${time}`;
										}
										return date;
									}}
								>
									{#snippet formatter({ value })}
										<div class="flex flex-1 items-center justify-between gap-4">
											<span class="text-muted-foreground">Temp</span>
											<span class="font-mono font-medium tabular-nums">
												{Number(value).toFixed(2)}{unitSymbol}
											</span>
										</div>
									{/snippet}
								</Chart.Tooltip>
							{/snippet}
						</LineChart>
					</Chart.Container>
			</div>

		{:else if chartData.length === 0}
			<div class="rounded-md border bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
				No nearby pixel found within tolerance.
			</div>
		{/if}

		<!-- Compact table -->
		{#if rows.length > 0}
			<div class="rounded-md border overflow-hidden">
				<div class="max-h-52 overflow-y-auto">
					<table class="w-full text-xs">
						<thead class="sticky top-0 z-10 bg-background">
							<tr class="border-b text-muted-foreground">
								<th class="text-left px-2 py-1.5 font-medium">Date</th>
								<th class="text-right px-2 py-1.5 font-medium">Temp</th>
								<th class="text-right px-2 py-1.5 font-medium">Dist</th>
							</tr>
						</thead>
						<tbody>
							{#each rows as row (row.date)}
								<tr
									class="border-t border-border/40 hover:bg-muted/30 transition-colors cursor-pointer {row.date === selectedDate ? 'bg-primary/10' : ''}"
									onmouseenter={() => handleRowHover(row)}
									onmouseleave={() => handleRowHover(null)}
									onclick={() => ondatechange?.(row.date)}
								>
									<td class="px-2 py-1 tabular-nums text-nowrap">{fmtTableDate(row.date)}</td>
									<td class="px-2 py-1 text-right tabular-nums font-medium text-nowrap">
										{row.displayTemperature.toFixed(1)}{unitSymbol}
									</td>
									<td class="px-2 py-1 text-right text-muted-foreground tabular-nums text-nowrap">
										{formatDistance(row.distance)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	{/if}
</div>
