<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { goto } from '$app/navigation';
	import * as Select from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import { ScrollArea } from '$lib/components/ui/scroll-area';
	import { Separator } from '$lib/components/ui/separator';
	import { cn } from '$lib/utils.js';
	import ThermometerIcon from '@lucide/svelte/icons/thermometer';
	import PaletteIcon from '@lucide/svelte/icons/palette';
	import BarChart3Icon from '@lucide/svelte/icons/bar-chart-3';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import { BarChart } from 'layerchart';
	import { scaleBand } from 'd3-scale';

	export let featureId: string;
	export let featureName: string = '';
	export let isOpen: boolean = false;
	export let selectedDate: string = '';
	export let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	// Pre-computed stats from server (in Kelvin)
	export let relativeMin: number = 0;
	export let relativeMax: number = 0;
	export let avgTemp: number = 0;
	export let histogramData: Array<{ range: string; count: number }> = [];

	const dispatch = createEventDispatcher<{
		close: void;
		dateChange: string;
		colorScaleChange: 'relative' | 'fixed' | 'gray';
	}>();

	let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	let dates: string[] = [];
	let showWaterOffAlert = false;
	let loading = false;

	const globalMin = 273.15;
	const globalMax = 308.15;

	function resetState() {
		dates = [];
		selectedDate = '';
		showWaterOffAlert = false;
	}

	$: unitSymbol = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F';

	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}

	// Use server-provided stats (already in Kelvin)
	$: stats = relativeMin && relativeMax ? {
		min: convertTemp(relativeMin, currentUnit),
		max: convertTemp(relativeMax, currentUnit),
		avg: convertTemp(avgTemp, currentUnit)
	} : null;

	function formatDateTime(date: string): string {
		const year = date.substring(0, 4);
		const doy = parseInt(date.substring(4, 7), 10);
		const hours = date.substring(7, 9);
		const minutes = date.substring(9, 11);
		const seconds = date.substring(11, 13);
		const dateObj = new Date(parseInt(year), 0);
		dateObj.setDate(doy);
		const day = String(dateObj.getDate()).padStart(2, '0');
		const month = String(dateObj.getMonth() + 1).padStart(2, '0');
		return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
	}

	function formatShortDate(date: string): string {
		const year = date.substring(0, 4);
		const doy = parseInt(date.substring(4, 7), 10);
		const dateObj = new Date(parseInt(year), 0);
		dateObj.setDate(doy);
		return dateObj.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
	}

	async function loadDates() {
		if (!featureId) return;
		loading = true;
		try {
			const response = await fetch(`/api/feature/${featureId}/get_dates`);
			const fetchedDates = await response.json();
			dates = Array.isArray(fetchedDates) ? fetchedDates : [];
			if (dates.length > 0) {
				selectedDate = dates[0];
				dispatch('dateChange', selectedDate);
				// Temperature data is loaded by parent via handleDateChange
			}
		} catch (err) {
			console.error('Error loading dates:', err);
			dates = [];
		} finally {
			loading = false;
		}
	}

	async function checkWaterOff() {
		if (!selectedDate || !featureId) return;
		try {
			const response = await fetch(`/api/feature/${featureId}/check_wtoff/${selectedDate}`);
			const data = (await response.json()) as { wtoff?: boolean };
			showWaterOffAlert = Boolean(data.wtoff);
		} catch (err) {
			console.error('Error checking water off:', err);
		}
	}

	// Convert server histogram ranges to current unit
	$: convertedHistogram = histogramData.map(bin => ({
		range: convertTemp(parseFloat(bin.range), currentUnit).toFixed(1),
		count: bin.count
	}));

	function handleDateChange(value: string) {
		selectedDate = value;
		dispatch('dateChange', selectedDate);
		// Temperature data is loaded by parent via handleDateChange
		checkWaterOff();
	}

	function handleColorScaleChange(value: 'relative' | 'fixed' | 'gray') {
		selectedColorScale = value;
		dispatch('colorScaleChange', selectedColorScale);
	}

	$: if (featureId && isOpen) {
		resetState();
		loadDates();
	}
	$: if (selectedDate && featureId) {
		checkWaterOff();
	}
</script>

<div class="flex flex-col h-full">
	{#if loading}
		<div class="flex flex-col items-center justify-center py-16 gap-4">
			<Spinner class="size-8 text-muted-foreground" />
			<p class="text-sm text-muted-foreground">Loading data...</p>
		</div>
	{:else if dates.length === 0}
		<div class="flex flex-col items-center justify-center py-16 text-center px-4">
			<div class="rounded-full bg-muted p-4 mb-4">
				<ThermometerIcon class="size-8 text-muted-foreground" />
			</div>
			<p class="font-medium text-foreground mb-1">No data yet</p>
			<p class="text-sm text-muted-foreground">
				{featureName ? `${featureName} doesn't have temperature observations yet.` : 'This water body has no temperature observations.'}
			</p>
		</div>
	{:else}
		<ScrollArea class="flex-1">
			<div class="p-4 space-y-6">
				<!-- Summary line -->
				<p class="text-sm text-muted-foreground">
					{dates.length} observation{dates.length === 1 ? '' : 's'}
					{#if selectedDate}
						· {formatShortDate(selectedDate)}
					{/if}
				</p>

				{#if showWaterOffAlert}
					<Alert variant="destructive" class="py-2">
						<AlertDescription class="text-sm">Water not detected — data may include land pixels.</AlertDescription>
					</Alert>
				{/if}

				<!-- Map overlay -->
				<div class="space-y-3">
					<h3 class="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-2">
						<PaletteIcon class="size-3.5" />
						Map overlay
					</h3>
					<div class="grid gap-3">
						<div>
							<label for="date-select" class="text-xs text-muted-foreground mb-1.5 block">Date</label>
							<Select.Root type="single" value={selectedDate} onValueChange={(v) => v != null && handleDateChange(v)}>
								<Select.Trigger id="date-select" class="w-full h-9">
									<span class="truncate">{selectedDate ? formatDateTime(selectedDate) : 'Pick date'}</span>
								</Select.Trigger>
								<Select.Content>
									{#each dates as date}
										<Select.Item value={date} label={formatDateTime(date)}>
											{formatDateTime(date)}
										</Select.Item>
									{/each}
								</Select.Content>
							</Select.Root>
						</div>
						<div>
							<label for="scale-select" class="text-xs text-muted-foreground mb-1.5 block">Color scale</label>
							<Select.Root type="single" value={selectedColorScale} onValueChange={(v) => v != null && handleColorScaleChange(v as 'relative' | 'fixed' | 'gray')}>
								<Select.Trigger id="scale-select" class="w-full h-9">
									{selectedColorScale}
								</Select.Trigger>
								<Select.Content>
									<Select.Item value="relative" label="Relative">Relative</Select.Item>
									<Select.Item value="fixed" label="Fixed">Fixed</Select.Item>
									<Select.Item value="gray" label="Grayscale">Grayscale</Select.Item>
								</Select.Content>
							</Select.Root>
							<div
								class={cn(
									'mt-2 w-full h-2 rounded-full',
									selectedColorScale === 'gray' ? 'color-scale-gray' : 'color-scale-rainbow'
								)}
							></div>
							<div class="flex justify-between text-[10px] text-muted-foreground mt-1">
								<span>
									{selectedColorScale === 'relative'
										? convertTemp(relativeMin, currentUnit).toFixed(1)
										: convertTemp(globalMin, currentUnit).toFixed(0)}
								</span>
								<span>{unitSymbol}</span>
								<span>
									{selectedColorScale === 'relative'
										? convertTemp(relativeMax, currentUnit).toFixed(1)
										: convertTemp(globalMax, currentUnit).toFixed(0)}
								</span>
							</div>
						</div>
					</div>
				</div>

				<Separator />

				<!-- Temperature snapshot -->
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
								currentUnit === 'Kelvin' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
							)}
							onclick={() => (currentUnit = 'Kelvin')}
						>
							K
						</button>
						<button
							type="button"
							class={cn(
								'px-2.5 py-1 text-xs font-medium rounded transition-colors',
								currentUnit === 'Celsius' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
							)}
							onclick={() => (currentUnit = 'Celsius')}
						>
							°C
						</button>
						<button
							type="button"
							class={cn(
								'px-2.5 py-1 text-xs font-medium rounded transition-colors',
								currentUnit === 'Fahrenheit' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
							)}
							onclick={() => (currentUnit = 'Fahrenheit')}
						>
							°F
						</button>
					</div>
				</div>

				<!-- Distribution -->
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
											stroke: "none",
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

				<Separator />

				<!-- Primary CTA -->
				<Button class="w-full" variant="default" onclick={() => goto(`/archive/${featureId}`)}>
					<DownloadIcon class="size-4 mr-2" />
					View archive &amp; download
				</Button>
			</div>
		</ScrollArea>
	{/if}
</div>
