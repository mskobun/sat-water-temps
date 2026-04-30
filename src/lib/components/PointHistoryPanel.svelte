<script lang="ts">
	import { parseDate } from '$lib/date-utils';
	import { onMount } from 'svelte';
	import { tick } from 'svelte';
	import { mode } from 'mode-watcher';
	import EChartsWrapper from '$lib/components/ui/echarts/EChartsWrapper.svelte';
	import type { ECharts } from 'echarts/core';
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
	let parquetProgress: { loaded: number; total: number } | null = $state(null);

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
		parquetProgress = null;
		let unsubProgress: (() => void) | undefined;
		try {
			const source = (dataSource === 'landsat' ? 'landsat' : 'ecostress') as 'ecostress' | 'landsat';
			const duckdbCache = await getDuckDBCacheModule();
			if (!duckdbCache) return;
			unsubProgress = duckdbCache.parquetLoadProgress.subscribe((v) => { parquetProgress = v; });
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
			unsubProgress?.();
			parquetProgress = null;
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

		// Projected CRS (Landsat / ECOSTRESS STAC): fetch transform for exact quad
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

		// Fallback (no row/col or no CRS): rectangle from pixel center
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
			.map((r) => ({
				sourceDate: r.date,
				date: parseDate(r.date),
				temperature: r.displayTemperature
			}))
	);

	let chartColor = $state('#f97316');

	function resolveColor() {
		const style = getComputedStyle(document.documentElement);
		chartColor = style.getPropertyValue('--chart-1').trim() || '#f97316';
	}

	onMount(resolveColor);

	$effect(() => {
		if (mode.current !== undefined) tick().then(resolveColor);
	});

	let echartsOption = $derived({
		animation: false,
		grid: { top: 12, left: 44, bottom: 52, right: 16, containLabel: false },
		xAxis: {
			type: 'time' as const,
			axisLabel: {
				fontSize: 10,
				color: 'var(--muted-foreground)',
				formatter: (value: number) =>
					new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
			},
			axisLine: { lineStyle: { color: 'var(--border)' } },
			splitLine: { show: false }
		},
		yAxis: {
			type: 'value' as const,
			min: 'dataMin' as const,
			splitNumber: 4,
			axisLabel: {
				fontSize: 10,
				color: 'var(--muted-foreground)',
				formatter: (value: number) => `${value.toFixed(1)}${unitSymbol}`
			},
			axisLine: { show: false },
			splitLine: { lineStyle: { color: 'var(--border)', opacity: 0.5 } }
		},
		series: [
			{
				name: 'Temperature',
				type: 'line' as const,
				data: chartData.map((d) => [d.date, d.temperature]),
				smooth: true,
				symbol: 'circle',
				symbolSize: 5,
				itemStyle: { color: chartColor },
				lineStyle: { color: chartColor, width: 2 }
			}
		],
		dataZoom: [
			{
				type: 'slider' as const,
				xAxisIndex: 0,
				bottom: 4,
				height: 20,
				startValue: chartData.length > 10 ? chartData[chartData.length - 10].date.getTime() : undefined,
				endValue: chartData[chartData.length - 1]?.date.getTime(),
				borderColor: 'transparent',
				fillerColor: 'rgba(128,128,128,0.15)',
				handleStyle: { color: 'rgba(128,128,128,0.5)' },
				moveHandleStyle: { color: 'rgba(128,128,128,0.5)' },
				showDetail: false,
				brushSelect: false
			},
			{
				type: 'inside' as const,
				xAxisIndex: 0
			}
		],
		tooltip: {
			trigger: 'axis' as const,
			backgroundColor: 'var(--background)',
			borderColor: 'var(--border)',
			textStyle: { fontSize: 11, color: 'var(--foreground)' },
			formatter: (params: unknown) => {
				const items = params as Array<{ axisValue: number | Date; value: [Date, number] }>;
				if (!items?.length) return '';
				const date = new Date(items[0].axisValue);
				const dateStr = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
				const timeStr = (date.getHours() !== 0 || date.getMinutes() !== 0)
					? ', ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
					: '';
				const temp = Number(items[0].value[1]).toFixed(2);
				return `<div style="font-size:11px"><div style="margin-bottom:4px;opacity:0.7">${dateStr}${timeStr}</div><span style="margin-right:8px;opacity:0.7">Temp</span><b>${temp}${unitSymbol}</b></div>`;
			}
		}
	});

	function handleChartInit(instance: ECharts) {
		instance.on('click', (params: unknown) => {
			const p = params as { componentType: string; dataIndex: number };
			if (p.componentType !== 'series') return;
			const d = chartData[p.dataIndex];
			if (d?.sourceDate) ondatechange?.(d.sourceDate);
		});
	}

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
			{#if parquetProgress && parquetProgress.total > 0}
				<p class="text-xs text-muted-foreground">
					Querying · {(parquetProgress.loaded / 1_048_576).toFixed(1)} / {(parquetProgress.total / 1_048_576).toFixed(1)} MB
				</p>
			{:else}
				<p class="text-xs text-muted-foreground">Querying…</p>
			{/if}
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
			<div class="rounded-md border bg-muted/10">
				<EChartsWrapper
					option={echartsOption}
					class="h-56 w-full"
					onInit={handleChartInit}
				/>
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
