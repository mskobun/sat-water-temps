<script lang="ts">
	import { onDestroy } from 'svelte';
	import * as Select from '$lib/components/ui/select';
	import FeatureObservationCalendar from '$lib/components/FeatureObservationCalendar.svelte';
	import { Slider } from '$lib/components/ui/slider';
	import FilterIcon from '@lucide/svelte/icons/filter';
	import PaletteIcon from '@lucide/svelte/icons/palette';

	type Props = {
		featureId: string;
		selectedDate?: string;
		selectedColorScale?: 'relative' | 'fixed' | 'gray';
		currentUnit?: 'Kelvin' | 'Celsius' | 'Fahrenheit';
		dateEntries?: Array<{ date: string; source: string }>;
		relativeMin?: number;
		relativeMax?: number;
		initialFilterMin?: number | null;
		initialFilterMax?: number | null;
		onDateChange?: (value: string) => void;
		onColorScaleChange?: (value: 'relative' | 'fixed' | 'gray') => void;
		onTempFilterChange?: (value: { min: number | null; max: number | null }) => void;
	};

	let {
		featureId,
		selectedDate = $bindable(''),
		selectedColorScale = $bindable('relative'),
		currentUnit = 'Celsius',
		dateEntries = [],
		relativeMin = 0,
		relativeMax = 0,
		initialFilterMin = null,
		initialFilterMax = null,
		onDateChange,
		onColorScaleChange,
		onTempFilterChange
	}: Props = $props();

	// Apply initial filter values from URL once scale range is known
	let initialFilterApplied = false;
	$effect(() => {
		if (initialFilterApplied) return;
		if (initialFilterMin == null && initialFilterMax == null) return;
		if (scaleMin === 0 && scaleMax === 0) return; // data not loaded yet
		initialFilterApplied = true;
		const lo = initialFilterMin != null ? Math.max(0, Math.min(100, tempToPercent(initialFilterMin))) : 0;
		const hi = initialFilterMax != null ? Math.max(0, Math.min(100, tempToPercent(initialFilterMax))) : 100;
		filterRange = [lo, hi];
		// Dispatch immediately so parent applies the filter
		if (lo > 0 || hi < 100) {
			onTempFilterChange?.({ min: initialFilterMin, max: initialFilterMax });
		}
	});

	const globalMin = 273.15;
	const globalMax = 308.15;
	const colorScaleLabels = { relative: 'Relative', fixed: 'Fixed', gray: 'Grayscale' } as const;
	const FILTER_CHANGE_DEBOUNCE_MS = 100;

	let filterRange = $state([0, 100]);
	let filterChangeTimeout: ReturnType<typeof setTimeout> | null = null;

	let unitSymbol = $derived(
		currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F'
	);
	let scaleMin = $derived(selectedColorScale === 'relative' ? relativeMin : globalMin);
	let scaleMax = $derived(selectedColorScale === 'relative' ? relativeMax : globalMax);
	let filterMinTemp = $derived(scaleMin + (filterRange[0] / 100) * (scaleMax - scaleMin));
	let filterMaxTemp = $derived(scaleMin + (filterRange[1] / 100) * (scaleMax - scaleMin));
	let isFiltering = $derived(filterRange[0] > 0 || filterRange[1] < 100);

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

	function clearFilterChangeTimeout() {
		if (filterChangeTimeout !== null) {
			clearTimeout(filterChangeTimeout);
			filterChangeTimeout = null;
		}
	}

	function dispatchTempFilterChange(min: number | null, max: number | null, debounce = true) {
		clearFilterChangeTimeout();
		if (!debounce) {
			onTempFilterChange?.({ min, max });
			return;
		}
		filterChangeTimeout = setTimeout(() => {
			filterChangeTimeout = null;
			onTempFilterChange?.({ min, max });
		}, FILTER_CHANGE_DEBOUNCE_MS);
	}

	onDestroy(() => {
		clearFilterChangeTimeout();
	});

	function resetFilter() {
		filterRange = [0, 100];
		dispatchTempFilterChange(null, null, false);
	}

	export function resetControls() {
		resetFilter();
	}

	function handleDateChange(value: string) {
		selectedDate = value;
		onDateChange?.(selectedDate);
	}

	function handleColorScaleChange(value: 'relative' | 'fixed' | 'gray') {
		selectedColorScale = value;
		onColorScaleChange?.(selectedColorScale);
		resetFilter();
	}

	function handleFilterRangeChange(values: number[]) {
		filterRange = values;
		if (values[0] === 0 && values[1] === 100) {
			dispatchTempFilterChange(null, null);
		} else {
			dispatchTempFilterChange(percentToTemp(values[0]), percentToTemp(values[1]));
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
					{#each Object.entries(colorScaleLabels) as [value, label] (value)}
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
