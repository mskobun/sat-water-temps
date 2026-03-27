<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import * as Select from '$lib/components/ui/select';
	import FeatureObservationCalendar from '$lib/components/FeatureObservationCalendar.svelte';
	import { Slider } from '$lib/components/ui/slider';
	import FilterIcon from '@lucide/svelte/icons/filter';
	import PaletteIcon from '@lucide/svelte/icons/palette';

	export let featureId: string;
	export let selectedDate: string = '';
	export let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	export let dateEntries: Array<{ date: string; source: string }> = [];
	export let relativeMin: number = 0;
	export let relativeMax: number = 0;

	const dispatch = createEventDispatcher<{
		dateChange: string;
		colorScaleChange: 'relative' | 'fixed' | 'gray';
		tempFilterChange: { min: number | null; max: number | null };
	}>();

	const globalMin = 273.15;
	const globalMax = 308.15;
	const colorScaleLabels = { relative: 'Relative', fixed: 'Fixed', gray: 'Grayscale' } as const;

	let filterRange: number[] = [0, 100];

	$: unitSymbol = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F';
	$: scaleMin = selectedColorScale === 'relative' ? relativeMin : globalMin;
	$: scaleMax = selectedColorScale === 'relative' ? relativeMax : globalMax;
	$: filterMinTemp = scaleMin + (filterRange[0] / 100) * (scaleMax - scaleMin);
	$: filterMaxTemp = scaleMin + (filterRange[1] / 100) * (scaleMax - scaleMin);
	$: isFiltering = filterRange[0] > 0 || filterRange[1] < 100;

	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}

	function percentToTemp(percent: number): number {
		return scaleMin + (percent / 100) * (scaleMax - scaleMin);
	}

	function tempToPercent(temp: number): number {
		if (scaleMax === scaleMin) return 0;
		return ((temp - scaleMin) / (scaleMax - scaleMin)) * 100;
	}

	function resetFilter() {
		filterRange = [0, 100];
		dispatch('tempFilterChange', { min: null, max: null });
	}

	export function resetControls() {
		resetFilter();
	}

	function handleDateChange(value: string) {
		selectedDate = value;
		dispatch('dateChange', selectedDate);
	}

	function handleColorScaleChange(value: 'relative' | 'fixed' | 'gray') {
		selectedColorScale = value;
		dispatch('colorScaleChange', selectedColorScale);
		resetFilter();
	}

	function handleFilterRangeChange(values: number[]) {
		filterRange = values;
		if (values[0] === 0 && values[1] === 100) {
			dispatch('tempFilterChange', { min: null, max: null });
		} else {
			dispatch('tempFilterChange', { min: percentToTemp(values[0]), max: percentToTemp(values[1]) });
		}
	}

	function handleMinInputChange(e: Event) {
		const input = e.target as HTMLInputElement;
		const displayValue = parseFloat(input.value);
		if (Number.isNaN(displayValue)) return;
		let kelvin: number;
		if (currentUnit === 'Celsius') kelvin = displayValue + 273.15;
		else if (currentUnit === 'Fahrenheit') kelvin = (displayValue - 32) * 5 / 9 + 273.15;
		else kelvin = displayValue;
		const percent = Math.max(0, Math.min(100, tempToPercent(kelvin)));
		filterRange = [Math.min(percent, filterRange[1]), filterRange[1]];
		handleFilterRangeChange(filterRange);
	}

	function handleMaxInputChange(e: Event) {
		const input = e.target as HTMLInputElement;
		const displayValue = parseFloat(input.value);
		if (Number.isNaN(displayValue)) return;
		let kelvin: number;
		if (currentUnit === 'Celsius') kelvin = displayValue + 273.15;
		else if (currentUnit === 'Fahrenheit') kelvin = (displayValue - 32) * 5 / 9 + 273.15;
		else kelvin = displayValue;
		const percent = Math.max(0, Math.min(100, tempToPercent(kelvin)));
		filterRange = [filterRange[0], Math.max(percent, filterRange[0])];
		handleFilterRangeChange(filterRange);
	}
</script>

<div class="space-y-3">
	<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
		<PaletteIcon class="size-3.5" />
		Map overlay
	</h3>
	<div class="grid gap-3">
		<div>
			<p id="observation-calendar-label" class="text-xs text-muted-foreground mb-1.5">Date</p>
			<div aria-labelledby="observation-calendar-label">
				<FeatureObservationCalendar
					{selectedDate}
					{dateEntries}
					{featureId}
					colorScale={selectedColorScale}
					onSelect={handleDateChange}
				/>
			</div>
		</div>
		<div>
			<label for="scale-select" class="text-xs text-muted-foreground mb-1.5 block">Color scale</label>
			<Select.Root
				type="single"
				value={selectedColorScale}
				onValueChange={(v) => v != null && handleColorScaleChange(v as 'relative' | 'fixed' | 'gray')}
			>
				<Select.Trigger id="scale-select" class="w-full h-9">
					{colorScaleLabels[selectedColorScale]}
				</Select.Trigger>
				<Select.Content>
					{#each Object.entries(colorScaleLabels) as [value, label]}
						<Select.Item {value} {label}>{label}</Select.Item>
					{/each}
				</Select.Content>
			</Select.Root>
		</div>
		<div class="space-y-2">
			<label class="text-xs text-muted-foreground flex items-baseline gap-1.5">
				<FilterIcon class="size-3 relative top-px" />
				Temperature filter
				{#if isFiltering}
					<button
						type="button"
						class="text-[10px] text-primary font-medium hover:underline"
						onclick={resetFilter}
					>
						Reset
					</button>
				{/if}
			</label>
			<Slider
				type="multiple"
				value={filterRange}
				onValueChange={handleFilterRangeChange}
				min={0}
				max={100}
				step={0.5}
				class="w-full"
				trackClass={selectedColorScale === 'gray' ? 'color-scale-gray' : 'color-scale-rainbow'}
				showRange={false}
			/>
			<div class="flex items-center justify-between gap-2">
				<div class="flex items-center gap-1">
					<input
						type="number"
						step="0.1"
						value={convertTemp(filterMinTemp, currentUnit).toFixed(1)}
						onchange={handleMinInputChange}
						class="w-16 h-7 px-2 text-xs tabular-nums bg-muted border border-border rounded text-center focus:outline-none focus:ring-1 focus:ring-ring"
					/>
					<span class="text-[10px] text-muted-foreground">{unitSymbol}</span>
				</div>
				<span class="text-[10px] text-muted-foreground">to</span>
				<div class="flex items-center gap-1">
					<input
						type="number"
						step="0.1"
						value={convertTemp(filterMaxTemp, currentUnit).toFixed(1)}
						onchange={handleMaxInputChange}
						class="w-16 h-7 px-2 text-xs tabular-nums bg-muted border border-border rounded text-center focus:outline-none focus:ring-1 focus:ring-ring"
					/>
					<span class="text-[10px] text-muted-foreground">{unitSymbol}</span>
				</div>
			</div>
		</div>
	</div>
</div>
