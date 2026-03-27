<script lang="ts">
	import { BarChart } from 'layerchart';
	import { scaleBand } from 'd3-scale';
	import BarChart3Icon from '@lucide/svelte/icons/bar-chart-3';

	export let histogramData: Array<{ range: string; count: number }> = [];
	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';

	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}

	$: convertedHistogram = histogramData.map((bin) => ({
		range: convertTemp(parseFloat(bin.range), currentUnit).toFixed(1),
		count: bin.count
	}));
</script>

<div class="space-y-3">
	<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
		<BarChart3Icon class="size-3.5" />
		Distribution
	</h3>
	<div class="overflow-hidden">
		<div class="h-[200px] p-2">
			{#if convertedHistogram.length > 0}
				<BarChart
					data={convertedHistogram}
					x="range"
					xScale={scaleBand().padding(0.2)}
					y="count"
					yNice
					series={[{ key: 'count', color: 'var(--chart-1)' }]}
					props={{
						xAxis: { format: (d) => d },
						yAxis: { ticks: 4 },
						bars: {
							stroke: 'none'
						}
					}}
				/>
			{:else}
				<div class="h-full flex items-center justify-center text-muted-foreground text-sm">
					No data available
				</div>
			{/if}
		</div>
	</div>
</div>
