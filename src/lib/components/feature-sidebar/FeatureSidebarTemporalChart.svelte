<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { tick } from 'svelte';
	import { mode } from 'mode-watcher';
	import { parseDate } from '$lib/date-utils';
	import EChartsWrapper from '$lib/components/ui/echarts/EChartsWrapper.svelte';
	import Clock3Icon from '@lucide/svelte/icons/clock-3';
	import type { ECharts } from 'echarts/core';

	type FeatureStatsHistoryEntry = {
		date: string;
		source: string;
		min_temp: number | null;
		max_temp: number | null;
		mean_temp: number | null;
		median_temp: number | null;
		std_dev: number | null;
		data_points: number | null;
		water_pixel_count: number | null;
		land_pixel_count: number | null;
	};

	export let entries: FeatureStatsHistoryEntry[] = [];
	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	export const selectedDate: string = '';
	export let dataSource: string = '';
	const dispatch = createEventDispatcher<{ dateChange: string }>();

	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}

	$: unitSymbol = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F';
	$: filteredEntries = dataSource
		? entries.filter((entry) => entry.source === dataSource)
		: entries;

	$: chartData = [...filteredEntries]
		.reverse()
		.map((entry) => ({
			sourceDate: entry.date,
			date: parseDate(entry.date),
			min: entry.min_temp == null ? null : convertTemp(entry.min_temp, currentUnit),
			mean: entry.mean_temp == null ? null : convertTemp(entry.mean_temp, currentUnit),
			median: entry.median_temp == null ? null : convertTemp(entry.median_temp, currentUnit),
			max: entry.max_temp == null ? null : convertTemp(entry.max_temp, currentUnit)
		}))
		.filter(
			(point) =>
				point.min != null &&
				point.mean != null &&
				point.median != null &&
				point.max != null
		);

	function makeSeriesData(valueKey: 'min' | 'mean' | 'median' | 'max') {
		return chartData.map((d) => ({
			value: [d.date.getTime(), d[valueKey]],
			sourceDate: d.sourceDate
		}));
	}

	let chartColors = ['#f97316', '#14b8a6', '#374151', '#eab308'];

	function resolveColors() {
		const style = getComputedStyle(document.documentElement);
		chartColors = [1, 2, 3, 4].map(
			(i) => style.getPropertyValue(`--chart-${i}`).trim() || chartColors[i - 1]
		);
	}

	onMount(resolveColors);
	$: if (mode.current !== undefined) tick().then(resolveColors);

	$: echartsOption = {
		animation: false,
		grid: { top: 12, left: 52, bottom: 52, right: 16, containLabel: false },
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
		series: (
			[
				{ name: 'Min',    data: makeSeriesData('min'),    color: chartColors[0] },
				{ name: 'Mean',   data: makeSeriesData('mean'),   color: chartColors[1] },
				{ name: 'Median', data: makeSeriesData('median'), color: chartColors[2] },
				{ name: 'Max',    data: makeSeriesData('max'),    color: chartColors[3] }
			] as const
		).map(({ name, data, color }) => ({
			name,
			type: 'line' as const,
			data,
			smooth: true,
			symbol: 'circle',
			symbolSize: 5,
			itemStyle: { color },
			lineStyle: { color, width: 2 },
			emphasis: { focus: 'none' as const, disabled: true },
			blur: { lineStyle: { opacity: 1 }, itemStyle: { opacity: 1 } }
		})),
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
				emphasis: { handleStyle: { color: 'rgba(128,128,128,0.8)' } },
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
				const items = params as Array<{ axisValue: number | Date; seriesName: string; value: [Date, number] }>;
				if (!items?.length) return '';
				const date = new Date(items[0].axisValue);
				const dateStr = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
				const rows = items
					.map((p) => `<span style="margin-right:8px">${p.seriesName}</span><b>${Number(p.value[1]).toFixed(1)}${unitSymbol}</b>`)
					.join('<br>');
				return `<div style="font-size:11px"><div style="margin-bottom:4px;opacity:0.7">${dateStr}</div>${rows}</div>`;
			}
		}
	};

	function handleInit(instance: ECharts) {
		instance.on('click', (params: unknown) => {
			const p = params as {
				componentType: string;
				data?: { sourceDate?: string };
				dataIndex?: number;
			};
			if (p.componentType !== 'series') return;
			const date = p.data?.sourceDate ?? (p.dataIndex != null ? chartData[p.dataIndex]?.sourceDate : null);
			if (date) dispatch('dateChange', date);
		});
	}
</script>

<div class="space-y-3">
	<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
		<Clock3Icon class="size-3.5" />
		Temporal trends
	</h3>

	{#if chartData.length > 1}
		<div class="rounded-md border bg-muted/10">
			<EChartsWrapper
				option={echartsOption}
				class="h-64 w-full"
				onInit={handleInit}
			/>
		</div>
		<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full" style="background:{chartColors[0]}"></span>
				Min
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full" style="background:{chartColors[1]}"></span>
				Mean
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full" style="background:{chartColors[2]}"></span>
				Median
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full" style="background:{chartColors[3]}"></span>
				Max
			</span>
		</div>
	{:else}
		<div class="rounded-md border bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
			Need at least two observations to show temporal trends.
		</div>
	{/if}
</div>
