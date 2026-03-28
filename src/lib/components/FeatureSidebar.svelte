<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import FeatureSidebarHeader from '$lib/components/feature-sidebar/FeatureSidebarHeader.svelte';
	import FeatureSidebarOverlayControls from '$lib/components/feature-sidebar/FeatureSidebarOverlayControls.svelte';
	import FeatureSidebarSnapshot from '$lib/components/feature-sidebar/FeatureSidebarSnapshot.svelte';
	import FeatureSidebarTemporalChart from '$lib/components/feature-sidebar/FeatureSidebarTemporalChart.svelte';
	import FeatureSidebarDistribution from '$lib/components/feature-sidebar/FeatureSidebarDistribution.svelte';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import { ScrollArea } from '$lib/components/ui/scroll-area';
	import { Separator } from '$lib/components/ui/separator';
	import ThermometerIcon from '@lucide/svelte/icons/thermometer';
	import { page } from '$app/stores';

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

	export let featureId: string;
	export let featureName: string = '';
	export let selectedDate: string = '';
	export let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	// Pre-computed stats from server (in Kelvin)
	export let relativeMin: number = 0;
	export let relativeMax: number = 0;
	export let avgTemp: number = 0;
	export let histogramData: Array<{ range: string; count: number }> = [];
	// Temperature unit (shared with parent for tooltip)
	export let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Celsius';
	// Water off status (passed from parent, fetched with temperature data)
	export let waterOff: boolean = false;
	export let temperatureLoading: boolean = false;
	export let initialDate: string = '';
	export let initialFilterMin: number | null = null;
	export let initialFilterMax: number | null = null;

	$: session = $page.data.session;

	export let dataSource: string = '';

	const dispatch = createEventDispatcher<{
		close: void;
		dateChange: string;
		colorScaleChange: 'relative' | 'fixed' | 'gray';
		tempFilterChange: { min: number | null; max: number | null };
	}>();
	let dateEntries: Array<{ date: string; source: string }> = [];
	let dates: string[] = [];
	let temporalStatsEntries: FeatureStatsHistoryEntry[] = [];
	let loading = false;
	let overlayControlsRef: FeatureSidebarOverlayControls | null = null;

	function resetState() {
		dates = [];
		dateEntries = [];
		temporalStatsEntries = [];
		selectedDate = '';
		dataSource = '';
		dispatch('tempFilterChange', { min: null, max: null });
		overlayControlsRef?.resetControls();
	}

	function getSourceForDate(date: string): string {
		const entry = dateEntries.find(e => e.date === date);
		return entry?.source || 'ecostress';
	}

	async function loadDates() {
		if (!featureId) return;
		loading = true;
		try {
			const enc = encodeURIComponent(featureId);
			const response = await fetch(`/api/feature/${enc}/get_dates`);
			const fetched = await response.json();
			// Handle both old format (string[]) and new format ({date, source}[])
			if (Array.isArray(fetched) && fetched.length > 0 && typeof fetched[0] === 'object') {
				dateEntries = fetched;
				dates = fetched.map((e: any) => e.date);
			} else {
				dateEntries = (Array.isArray(fetched) ? fetched : []).map((d: string) => ({ date: d, source: 'ecostress' }));
				dates = Array.isArray(fetched) ? fetched : [];
			}
			if (dates.length > 0) {
				selectedDate = (initialDate && dates.includes(initialDate)) ? initialDate : dates[0];
				dataSource = getSourceForDate(selectedDate);
				dispatch('dateChange', selectedDate);
			}
		} catch (err) {
			console.error('Error loading dates:', err);
			dates = [];
			dateEntries = [];
		} finally {
			loading = false;
		}
	}

	async function loadTemporalStats() {
		if (!featureId) return;
		try {
			const enc = encodeURIComponent(featureId);
			const response = await fetch(`/api/feature/${enc}/stats`);
			const payload = await response.json();
			const entries = Array.isArray(payload?.entries) ? payload.entries : [];
			// Cap chart history to avoid heavy multi-series rendering on very long records.
			temporalStatsEntries = entries.slice(0, 365);
		} catch (err) {
			console.error('Error loading temporal stats:', err);
			temporalStatsEntries = [];
		}
	}

	function handleDateChange(value: string) {
		selectedDate = value;
		dataSource = getSourceForDate(value);
		dispatch('dateChange', selectedDate);
		// Temperature data (including waterOff) is loaded by parent via handleDateChange
	}

	function handleColorScaleChange(value: 'relative' | 'fixed' | 'gray') {
		selectedColorScale = value;
		dispatch('colorScaleChange', selectedColorScale);
	}

	let prevFeatureId: string | undefined;
	$: if (featureId && featureId !== prevFeatureId) {
		prevFeatureId = featureId;
		resetState();
		void Promise.all([loadDates(), loadTemporalStats()]);
	}

	// Arrow key date navigation (same source only)
	function isInputFocused(): boolean {
		const el = document.activeElement;
		return (
			el instanceof HTMLInputElement ||
			el instanceof HTMLTextAreaElement ||
			(el instanceof HTMLElement && el.isContentEditable)
		);
	}

	export function navigateDate(direction: -1 | 1) {
		if (!featureId || !selectedDate || dateEntries.length === 0) return;
		// Filter to entries matching current data source
		const sameSourceEntries = dateEntries.filter(e => e.source === dataSource);
		const currentIndex = sameSourceEntries.findIndex(e => e.date === selectedDate);
		if (currentIndex === -1) return;
		// Dates are sorted DESC (newest first): ArrowRight = newer (index - 1), ArrowLeft = older (index + 1)
		const nextIndex = currentIndex - direction;
		if (nextIndex < 0 || nextIndex >= sameSourceEntries.length) return;
		handleDateChange(sameSourceEntries[nextIndex].date);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!featureId || !e.altKey || isInputFocused()) return;
		if (e.key === 'ArrowLeft') {
			e.preventDefault();
			navigateDate(-1); // older
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			navigateDate(1); // newer
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

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
				<FeatureSidebarHeader
					{featureId}
					{selectedDate}
					{dataSource}
					observationCount={dates.length}
					showAdminActions={Boolean(session?.user)}
				/>

			{#if waterOff}
				<Alert variant="destructive" class="py-2">
					<AlertDescription class="text-sm">Water not detected — data may include land pixels.</AlertDescription>
				</Alert>
			{/if}

				<FeatureSidebarOverlayControls
					bind:this={overlayControlsRef}
					{featureId}
					bind:selectedDate
					bind:selectedColorScale
					{currentUnit}
					{dateEntries}
					{relativeMin}
					{relativeMax}
					{initialFilterMin}
					{initialFilterMax}
					onDateChange={handleDateChange}
					onColorScaleChange={handleColorScaleChange}
					onTempFilterChange={(value) => dispatch('tempFilterChange', value)}
				/>

				<Separator />

				{#if temperatureLoading}
					<div class="flex flex-col items-center justify-center py-12 gap-3">
						<Spinner class="size-6 text-muted-foreground" />
						<p class="text-sm text-muted-foreground">Loading temperature data...</p>
					</div>
				{:else}
					<FeatureSidebarSnapshot
						bind:currentUnit
						{relativeMin}
						{relativeMax}
						{avgTemp}
					/>

					<FeatureSidebarTemporalChart
						entries={temporalStatsEntries}
						{currentUnit}
						{selectedDate}
						{dataSource}
						on:dateChange={(event) => handleDateChange(event.detail)}
					/>

					<FeatureSidebarDistribution
						{histogramData}
						{currentUnit}
					/>
				{/if}

				</div>
		</ScrollArea>
	{/if}
</div>
