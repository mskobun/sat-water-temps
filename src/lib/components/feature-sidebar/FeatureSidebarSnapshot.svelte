<script lang="ts">
	import { cn } from '$lib/utils.js';
	import ThermometerIcon from '@lucide/svelte/icons/thermometer';

	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	export let relativeMin: number = 0;
	export let relativeMax: number = 0;
	export let avgTemp: number = 0;

	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}

	$: unitSymbol = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F';
	$: stats = relativeMin && relativeMax
		? {
				min: convertTemp(relativeMin, currentUnit),
				max: convertTemp(relativeMax, currentUnit),
				avg: convertTemp(avgTemp, currentUnit)
			}
		: null;
</script>

<div class="space-y-3">
	<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
		<ThermometerIcon class="size-3.5" />
		Temperature
	</h3>
	{#if stats}
		<div class="grid grid-cols-3 gap-2">
			<div class="rounded-lg border bg-muted/40 px-3 py-2 text-center">
				<p class="text-[10px] text-muted-foreground uppercase tracking-wider">Min</p>
				<p class="text-sm font-semibold tabular-nums">{stats.min.toFixed(1)}{unitSymbol}</p>
			</div>
			<div class="rounded-lg border bg-muted/40 px-3 py-2 text-center">
				<p class="text-[10px] text-muted-foreground uppercase tracking-wider">Avg</p>
				<p class="text-sm font-semibold tabular-nums">{stats.avg.toFixed(1)}{unitSymbol}</p>
			</div>
			<div class="rounded-lg border bg-muted/40 px-3 py-2 text-center">
				<p class="text-[10px] text-muted-foreground uppercase tracking-wider">Max</p>
				<p class="text-sm font-semibold tabular-nums">{stats.max.toFixed(1)}{unitSymbol}</p>
			</div>
		</div>
	{/if}
	<div class="flex items-center gap-1 p-1 rounded-md bg-muted/50 w-fit">
		<button
			type="button"
			class={cn(
				'px-2.5 py-1 text-xs font-medium rounded transition-colors',
				currentUnit === 'Kelvin'
					? 'bg-background text-foreground shadow-sm'
					: 'text-muted-foreground hover:text-foreground'
			)}
			onclick={() => (currentUnit = 'Kelvin')}
		>
			K
		</button>
		<button
			type="button"
			class={cn(
				'px-2.5 py-1 text-xs font-medium rounded transition-colors',
				currentUnit === 'Celsius'
					? 'bg-background text-foreground shadow-sm'
					: 'text-muted-foreground hover:text-foreground'
			)}
			onclick={() => (currentUnit = 'Celsius')}
		>
			°C
		</button>
		<button
			type="button"
			class={cn(
				'px-2.5 py-1 text-xs font-medium rounded transition-colors',
				currentUnit === 'Fahrenheit'
					? 'bg-background text-foreground shadow-sm'
					: 'text-muted-foreground hover:text-foreground'
			)}
			onclick={() => (currentUnit = 'Fahrenheit')}
		>
			°F
		</button>
	</div>
</div>
