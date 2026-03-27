<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import * as Chart from '$lib/components/ui/chart';
	import { parseDate } from '$lib/date-utils';
	import { LineChart } from 'layerchart';
	import { scaleUtc } from 'd3-scale';
	import Clock3Icon from '@lucide/svelte/icons/clock-3';

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
		wtoff: boolean;
	};

	export let entries: FeatureStatsHistoryEntry[] = [];
	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	export let selectedDate: string = '';
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

	function resolveDateFromDetails(details: unknown): string | null {
		if (!details || typeof details !== 'object') return null;
		const detailObj = details as Record<string, unknown>;
		const data = detailObj.data as Record<string, unknown> | undefined;
		if (!data) return null;

		if (typeof data.sourceDate === 'string') return data.sourceDate;

		const x = data.x;
		const xDate =
			x instanceof Date
				? x
				: typeof x === 'string' || typeof x === 'number'
					? new Date(x)
					: null;
		if (!xDate || Number.isNaN(xDate.getTime())) return null;

		const match = filteredEntries.find((entry) => parseDate(entry.date).getTime() === xDate.getTime());
		return match?.date ?? null;
	}

	function handlePointClick(_e: MouseEvent, details: unknown) {
		const date = resolveDateFromDetails(details);
		if (date) dispatch('dateChange', date);
	}

	const chartConfig = {
		min: { label: 'Min', color: 'var(--chart-1)' },
		mean: { label: 'Mean', color: 'var(--chart-2)' },
		median: { label: 'Median', color: 'var(--chart-3)' },
		max: { label: 'Max', color: 'var(--chart-4)' }
	} satisfies Chart.ChartConfig;
</script>

<div class="space-y-3">
	<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
		<Clock3Icon class="size-3.5" />
		Temporal trends
	</h3>

	{#if chartData.length > 1}
		<div class="rounded-md border bg-muted/10 px-1 pb-1">
			<Chart.Container config={chartConfig} class="h-52 w-full">
				<LineChart
					data={chartData}
					x="date"
					xScale={scaleUtc()}
					axis={true}
					padding={{ top: 12, left: 52, bottom: 24, right: 24 }}
					points={{ r: 2.5 }}
					series={[
						{ key: 'min', label: 'Min', color: chartConfig.min.color },
						{ key: 'mean', label: 'Mean', color: chartConfig.mean.color },
						{ key: 'median', label: 'Median', color: chartConfig.median.color },
						{ key: 'max', label: 'Max', color: chartConfig.max.color }
					]}
					onPointClick={handlePointClick}
					props={{
						spline: { strokeWidth: 2 },
						xAxis: {
							format: (d: Date) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
						},
						yAxis: {
							ticks: 5,
							format: (v: number) => `${v.toFixed(1)}${unitSymbol}`
						}
					}}
				>
					{#snippet tooltip()}
						<Chart.Tooltip
							indicator="dot"
							labelFormatter={(v) =>
								v instanceof Date
									? v.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
									: String(v)}
						/>
					{/snippet}
				</LineChart>
			</Chart.Container>
		</div>
		<div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full bg-[var(--chart-1)]"></span>
				Min
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full bg-[var(--chart-2)]"></span>
				Mean
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full bg-[var(--chart-3)]"></span>
				Median
			</span>
			<span class="inline-flex items-center gap-1.5">
				<span class="size-2 rounded-full bg-[var(--chart-4)]"></span>
				Max
			</span>
		</div>
	{:else}
		<div class="rounded-md border bg-muted/10 px-3 py-2 text-xs text-muted-foreground">
			Need at least two observations to show temporal trends.
		</div>
	{/if}
</div>
