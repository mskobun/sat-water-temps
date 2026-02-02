<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { goto } from '$app/navigation';
	
	export let featureId: string;
	export let isOpen: boolean = false;
	export let selectedDate: string = '';
	export let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	
	const dispatch = createEventDispatcher<{
		close: void;
		dateChange: string;
		colorScaleChange: 'relative' | 'fixed' | 'gray';
	}>();
	
	let chartElement: HTMLCanvasElement;
	let chart: any = null;
	
	let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Kelvin';
	let temperatureData: any[] = [];
	let dates: string[] = [];
	let selectedGraphType: 'summary' | 'histogram' | 'line' | 'scatter' = 'summary';
	let showWaterOffAlert = false;
	let loading = false;
	
	let relativeMin = 0;
	let relativeMax = 0;
	const globalMin = 273.15;
	const globalMax = 308.15;
	
	function resetState() {
		// Clear all data
		dates = [];
		temperatureData = [];
		selectedDate = '';
		showWaterOffAlert = false;
		relativeMin = 0;
		relativeMax = 0;
		
		// Destroy chart if exists
		if (chart) {
			chart.destroy();
			chart = null;
		}
	}
	
	$: unitSymbol = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Celsius' ? '°C' : '°F';
	
	// Convert temperature based on unit
	function convertTemp(kelvin: number, unit: 'Kelvin' | 'Celsius' | 'Fahrenheit'): number {
		if (unit === 'Celsius') return kelvin - 273.15;
		if (unit === 'Fahrenheit') return (kelvin - 273.15) * 9/5 + 32;
		return kelvin;
	}
	
	$: convertedTemperatureData = temperatureData.map(point => {
		const kelvin = parseFloat(point.LST_filter || point.temperature || 0);
		return {
			...point,
			convertedTemp: convertTemp(kelvin, currentUnit)
		};
	});
	
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
				await loadTemperatureData(selectedDate);
			}
		} catch (err) {
			console.error('Error loading dates:', err);
			dates = [];
		} finally {
			loading = false;
		}
	}
	
	async function loadTemperatureData(date?: string) {
		if (!featureId) return;
		try {
			const url = date 
				? `/api/feature/${featureId}/temperature/${date}`
				: `/api/feature/${featureId}/temperature`;
			
			const response = await fetch(url);
			const data = await response.json() as { error?: string; data?: Array<{ x: number; y: number; temperature: number }>; min_max?: [number, number] };
			
			if (data.error) {
				console.error('Error:', data.error);
				return;
			}
			
			temperatureData = data.data || [];
			relativeMin = data.min_max?.[0] || 0;
			relativeMax = data.min_max?.[1] || 0;
			
			// Wait for DOM to update (canvas to be rendered) before updating chart
			await tick();
			updateChart();
		} catch (err) {
			console.error('Error loading temperature data:', err);
		}
	}
	
	async function checkWaterOff() {
		if (!selectedDate || !featureId) return;
		
		try {
			const response = await fetch(`/api/feature/${featureId}/check_wtoff/${selectedDate}`);
			const data = await response.json() as { wtoff?: boolean };
			showWaterOffAlert = Boolean(data.wtoff);
		} catch (err) {
			console.error('Error checking water off:', err);
		}
	}
	
	async function updateChart() {
		if (!chartElement || temperatureData.length === 0) return;
		
		const Chart = (await import('chart.js/auto')).default;
		
		if (chart) {
			chart.destroy();
		}
		
		const ctx = chartElement.getContext('2d');
		if (!ctx) return;
		
		const temps = temperatureData.map(p => parseFloat(p.LST_filter || p.temperature || 0));
		const convertedTemps = temps.map(t => convertTemp(t, currentUnit));
		const labels = temperatureData.map((_, i) => `Point ${i + 1}`);
		const latitudes = temperatureData.map(p => parseFloat(p.y || p.latitude || 0));
		
		let config: any = {
			type: 'line',
			data: { labels, datasets: [] },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					x: { title: { display: true, text: 'Data Points' } },
					y: { title: { display: true, text: `Temperature (${unitSymbol})` } }
				}
			}
		};
		
		switch (selectedGraphType) {
			case 'summary':
				config.type = 'bar';
				config.data.labels = ['Min', 'Max', 'Avg'];
				config.data.datasets.push({
					label: 'Statistics',
					data: [
						Math.min(...convertedTemps),
						Math.max(...convertedTemps),
						convertedTemps.reduce((a, b) => a + b, 0) / convertedTemps.length
					],
					backgroundColor: ['#4CAF50', '#F44336', '#2196F3']
				});
				break;
				
			case 'histogram':
				config.type = 'bar';
				const histData = createHistogram(convertedTemps, 5);
				config.data.labels = histData.labels;
				config.data.datasets.push({
					label: 'Temperature Distribution',
					data: histData.values,
					backgroundColor: '#9C27B0'
				});
				break;
				
			case 'line':
				config.data.datasets.push({
					label: `Temperature (${unitSymbol})`,
					data: convertedTemps,
					borderColor: '#ff7f0e',
					backgroundColor: 'rgba(255, 127, 14, 0.2)',
					borderWidth: 2,
					fill: true
				});
				break;
				
			case 'scatter':
				config.type = 'scatter';
				config.data.datasets.push({
					label: 'Temperature vs Latitude',
					data: latitudes.map((lat, i) => ({ x: lat, y: convertedTemps[i] })),
					backgroundColor: '#00BCD4',
					pointRadius: 5
				});
				config.options.scales.x.title.text = 'Latitude';
				break;
		}
		
		chart = new Chart(ctx, config);
	}
	
	function createHistogram(values: number[], binCount: number) {
		const min = Math.min(...values);
		const max = Math.max(...values);
		const binSize = (max - min) / binCount;
		
		const bins = Array(binCount).fill(0);
		const labels = [];
		
		for (let i = 0; i < binCount; i++) {
			const binStart = min + i * binSize;
			const binEnd = binStart + binSize;
			labels.push(`${binStart.toFixed(1)} - ${binEnd.toFixed(1)}`);
		}
		
		values.forEach(value => {
			let binIndex = Math.floor((value - min) / binSize);
			binIndex = Math.min(binIndex, binCount - 1);
			bins[binIndex]++;
		});
		
		return { labels, values: bins };
	}
	
	function handleDateChange(e: Event) {
		const target = e.target as HTMLSelectElement;
		selectedDate = target.value;
		dispatch('dateChange', selectedDate);
		loadTemperatureData(selectedDate);
		checkWaterOff();
	}
	
	function handleColorScaleChange(e: Event) {
		const target = e.target as HTMLSelectElement;
		selectedColorScale = target.value as 'relative' | 'fixed' | 'gray';
		dispatch('colorScaleChange', selectedColorScale);
	}
	
	function handleClose() {
		dispatch('close');
	}
	
	// Reactive updates when graph type or unit changes
	$: if ((selectedGraphType || currentUnit) && chartElement && temperatureData.length > 0) {
		updateChart();
	}
	
	// Load data when featureId changes
	$: if (featureId && isOpen) {
		resetState();
		loadDates();
	}
	
	// Check water off when date changes
	$: if (selectedDate && featureId) {
		checkWaterOff();
	}
</script>

<div 
	class="fixed top-0 right-0 h-screen w-[400px] bg-dark-surface/95 shadow-[-4px_0_20px_rgba(0,0,0,0.5)] z-[1000] transform transition-transform duration-300 ease-in-out backdrop-blur-md overflow-y-auto {isOpen ? 'translate-x-0' : 'translate-x-full'}"
>
	<!-- Close Button -->
	<button 
		class="absolute top-4 left-4 w-8 h-8 bg-red-500 hover:bg-red-600 text-white rounded-full border-none cursor-pointer text-xl font-bold transition-colors duration-200 flex items-center justify-center z-10"
		onclick={handleClose}
		aria-label="Close sidebar"
	>
		×
	</button>

	<div class="p-5 pt-14">
		<!-- Header -->
		<h2 class="text-center mb-4 text-lg font-semibold text-white">
			Temperature Data for <span class="text-cyan">{featureId}</span>
		</h2>

		{#if loading}
			<!-- Loading State -->
			<div class="flex flex-col items-center justify-center py-12">
				<div class="w-8 h-8 border-4 border-cyan border-t-transparent rounded-full animate-spin mb-4"></div>
				<p class="text-gray-400">Loading data...</p>
			</div>
		{:else if dates.length === 0}
			<!-- No Data State -->
			<div class="flex flex-col items-center justify-center py-12 text-center">
				<div class="text-4xl mb-4">📊</div>
				<p class="text-gray-400 text-lg mb-2">No data available</p>
				<p class="text-gray-500 text-sm">This lake doesn't have any temperature data yet.</p>
			</div>
		{:else}
			<!-- Water Off Alert -->
			{#if showWaterOffAlert}
				<div class="bg-amber-500 text-dark-bg px-4 py-2.5 rounded-md shadow-lg font-semibold mb-4 text-center text-sm">
					Water not detected - data may include land pixels
				</div>
			{/if}

			<!-- Date Selector -->
			<div class="bg-dark-card/80 p-3 rounded-lg mb-4">
				<label for="date-selector" class="text-white text-sm block mb-2">Select Date:</label>
				<select 
					id="date-selector" 
					value={selectedDate}
					onchange={handleDateChange}
					class="w-full py-2 px-3 rounded-md border-none bg-amber text-dark-bg font-bold cursor-pointer"
				>
					{#each dates as date}
						<option value={date}>{formatDateTime(date)}</option>
					{/each}
				</select>
			</div>

			<!-- Color Scale Selector -->
			<div class="bg-dark-card/80 p-3 rounded-lg mb-4">
				<label for="color-selector" class="text-white text-sm block mb-2">Color Scale:</label>
				<select 
					id="color-selector" 
					value={selectedColorScale}
					onchange={handleColorScaleChange}
					class="w-full py-2 px-3 rounded-md border-none bg-amber text-dark-bg font-bold cursor-pointer"
				>
					<option value="relative">Relative</option>
					<option value="fixed">Fixed</option>
					<option value="gray">Grayscale</option>
				</select>
				<div class="mt-2.5 w-full h-5 rounded-md relative {selectedColorScale === 'gray' ? 'color-scale-gray' : 'color-scale-rainbow'}">
					<span class="absolute top-6 left-0 text-xs text-white">
						{selectedColorScale === 'relative' ? convertTemp(relativeMin, currentUnit).toFixed(2) : convertTemp(globalMin, currentUnit).toFixed(2)}
					</span>
					<span class="absolute top-6 left-1/2 -translate-x-1/2 text-xs text-white">{unitSymbol}</span>
					<span class="absolute top-6 right-0 text-xs text-white">
						{selectedColorScale === 'relative' ? convertTemp(relativeMax, currentUnit).toFixed(2) : convertTemp(globalMax, currentUnit).toFixed(2)}
					</span>
				</div>
			</div>

			<!-- Unit Selector -->
			<div class="flex gap-2 justify-center mb-4">
				<button 
					class="px-3 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 text-sm {currentUnit === 'Kelvin' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
					onclick={() => currentUnit = 'Kelvin'}
				>
					Kelvin
				</button>
				<button 
					class="px-3 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 text-sm {currentUnit === 'Celsius' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
					onclick={() => currentUnit = 'Celsius'}
				>
					Celsius
				</button>
				<button 
					class="px-3 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 text-sm {currentUnit === 'Fahrenheit' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
					onclick={() => currentUnit = 'Fahrenheit'}
				>
					Fahrenheit
				</button>
			</div>

			<!-- Graph Container -->
			<div class="bg-dark-card/80 rounded-xl p-3 mb-4">
				<div class="flex justify-between items-center mb-2">
					<span class="text-white text-sm font-semibold">Chart</span>
					<select 
						bind:value={selectedGraphType} 
						class="py-1.5 px-2 rounded-md bg-amber text-dark-bg border-none font-bold cursor-pointer text-sm"
					>
						<option value="summary">Statistics</option>
						<option value="histogram">Distribution</option>
						<option value="line">Temperatures</option>
						<option value="scatter">Latitude</option>
					</select>
				</div>
				<div class="h-[250px]">
					<canvas bind:this={chartElement} class="w-full h-full"></canvas>
				</div>
			</div>

			<!-- Temperature Table -->
			<div class="w-full overflow-x-auto rounded-xl bg-white/5 shadow-[0_4px_15px_rgba(0,0,0,0.2)] mb-4">
				<table class="w-full text-white text-xs border-separate border-spacing-0 rounded-xl overflow-hidden">
					<thead>
						<tr>
							<th class="py-2.5 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Point</th>
							<th class="py-2.5 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">X</th>
							<th class="py-2.5 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Y</th>
							<th class="py-2.5 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Temp ({unitSymbol})</th>
						</tr>
					</thead>
					<tbody>
						{#each convertedTemperatureData.slice(0, 10) as point, i}
							<tr class="even:bg-white/[0.03] hover:bg-amber/15 transition-colors">
								<td class="py-2 px-2 border-b border-white/5 font-bold text-amber">{i + 1}</td>
								<td class="py-2 px-2 border-b border-white/5">{parseFloat(point.x || point.longitude || 0).toFixed(4)}</td>
								<td class="py-2 px-2 border-b border-white/5">{parseFloat(point.y || point.latitude || 0).toFixed(4)}</td>
								<td class="py-2 px-2 border-b border-white/5">{point.convertedTemp.toFixed(2)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Archive Button -->
			<button 
				class="w-full bg-blue-500/80 hover:bg-blue-500 text-white border-none py-3 px-4 rounded-lg font-bold cursor-pointer transition-colors duration-300"
				onclick={() => goto(`/archive/${featureId}`)}
			>
				Download All Data
			</button>
		{/if}
	</div>
</div>
