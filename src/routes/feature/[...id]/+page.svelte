<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	const featureId = $page.params.id;
	
	let mapElement: HTMLDivElement;
	let chartElement: HTMLCanvasElement;
	let map: any;
	let overlay: any = null;
	let polygon: any = null;
	let chart: any = null;
	
	let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = 'Kelvin';
	let temperatureData: any[] = [];
	let dates: string[] = [];
	let selectedDate = '';
	let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	let selectedGraphType: 'summary' | 'histogram' | 'line' | 'scatter' = 'summary';
	let showWaterOffAlert = false;
	
	let relativeMin = 0;
	let relativeMax = 0;
	const globalMin = 273.15;
	const globalMax = 308.15;
	
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
	
	async function initializeMap() {
		const L = await import('leaflet');
		
		map = L.map(mapElement, {
			center: [2.5, 112.5],
			zoom: 10,
			minZoom: 10,
			zoomControl: false
		});
		
		L.control.zoom({ position: 'bottomright' }).addTo(map);
		
		L.tileLayer(
			'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
			{
				attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community'
			}
		).addTo(map);
		
		// Load feature geometry
		try {
			const response = await fetch('/api/polygons');
			const geojson = await response.json();
			const feature = geojson.features.find((f: any) => f.properties && f.properties.name === featureId);
			
			if (!feature) {
				alert('Feature not found');
				return;
			}
			
			const coords = feature.geometry.coordinates;
			if (Array.isArray(coords) && Array.isArray(coords[0])) {
				const latLngs = coords[0].map((coord: number[]) => [coord[1], coord[0]]);
				polygon = L.polygon(latLngs, {
					color: '#8abbff',
					opacity: 0.05,
					weight: 2
				}).addTo(map);
				
				map.fitBounds(polygon.getBounds());
				map.setMaxBounds(polygon.getBounds());
				
				overlay = L.imageOverlay(`/api/latest_lst_tif/${featureId}`, polygon.getBounds()).addTo(map);
				
				map.on('zoomend', () => {
					polygon.setStyle({
						weight: 2 + map.getZoom() * 0.2,
						opacity: 0.05 + (map.getZoom() - 10) * 0.02
					});
				});
			}
		} catch (err) {
			console.error('Error loading polygons:', err);
		}
	}
	
	async function loadDates() {
		try {
			const response = await fetch(`/api/feature/${featureId}/get_dates`);
			dates = await response.json();
			if (dates.length > 0) {
				selectedDate = dates[0];
			}
		} catch (err) {
			console.error('Error loading dates:', err);
		}
	}
	
	async function loadTemperatureData(date?: string) {
		try {
			const url = date 
				? `/api/feature/${featureId}/temperature/${date}`
				: `/api/feature/${featureId}/temperature`;
			
			const response = await fetch(url);
			const data = await response.json();
			
			if (data.error) {
				console.error('Error:', data.error);
				return;
			}
			
			temperatureData = data.data || [];
			relativeMin = data.min_max?.[0] || 0;
			relativeMax = data.min_max?.[1] || 0;
			
			updateChart();
		} catch (err) {
			console.error('Error loading temperature data:', err);
		}
	}
	
	async function checkWaterOff() {
		if (!selectedDate) return;
		
		try {
			const response = await fetch(`/api/feature/${featureId}/check_wtoff/${selectedDate}`);
			const data = await response.json();
			showWaterOffAlert = data.wtoff || false;
		} catch (err) {
			console.error('Error checking water off:', err);
		}
	}
	
	function updateOverlay() {
		if (!map || !polygon || !selectedDate) return;
		
		const L = (window as any).L;
		
		// Remove existing overlay
		map.eachLayer((layer: any) => {
			if (layer instanceof L.ImageOverlay) {
				map.removeLayer(layer);
			}
		});
		
		// Add new overlay
		const newUrl = `/api/feature/${featureId}/tif/${selectedDate}/${selectedColorScale}`;
		overlay = L.imageOverlay(newUrl, polygon.getBounds()).addTo(map);
		
		checkWaterOff();
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
	
	// Reactive updates
	$: if (selectedDate) {
		loadTemperatureData(selectedDate);
		updateOverlay();
	}
	
	$: if (selectedColorScale) {
		updateOverlay();
	}
	
	$: if (selectedGraphType || currentUnit) {
		updateChart();
	}
	
	onMount(async () => {
		await Promise.all([
			initializeMap(),
			loadDates(),
			loadTemperatureData()
		]);
	});
</script>

<svelte:head>
	<title>{featureId} - Feature Details</title>
</svelte:head>

<div class="fixed inset-0 flex h-screen w-screen overflow-hidden bg-dark-bg z-10 font-poppins">
	<!-- Map Container -->
	<div class="flex-[3] relative">
		<div bind:this={mapElement} class="w-full h-screen brightness-90"></div>
		<button 
			class="absolute top-5 left-5 bg-blue-600 hover:bg-blue-800 text-white px-5 py-2.5 rounded-md font-bold text-base transition-colors duration-300 z-[1000] cursor-pointer"
			onclick={() => goto('/')}
		>
			Back
		</button>
	</div>

	<!-- Date Selector -->
	<div class="absolute top-5 left-1/2 -translate-x-1/2 bg-dark-surface/90 p-3 rounded-lg shadow-lg z-[999] backdrop-blur-sm">
		<label for="date-selector" class="text-white text-sm mr-2">Select Date:</label>
		<select 
			id="date-selector" 
			bind:value={selectedDate}
			class="py-1.5 px-3 rounded-md border-none bg-amber text-dark-bg font-bold cursor-pointer"
		>
			{#each dates as date}
				<option value={date}>{formatDateTime(date)}</option>
			{/each}
		</select>
	</div>

	<!-- Water Off Alert -->
	{#if showWaterOffAlert}
		<div class="absolute top-[70px] left-1/2 -translate-x-1/2 bg-red-500 text-white px-5 py-2.5 rounded-md shadow-lg z-[1001] font-semibold">
			<p class="m-0">Water Mask is off!</p>
		</div>
	{/if}

	<!-- Color Scale Selector -->
	<div class="absolute top-5 left-[70%] -translate-x-[30%] bg-dark-surface/90 p-3 rounded-lg shadow-lg z-[999] backdrop-blur-sm">
		<label for="color-selector" class="text-white text-sm mr-2">Color Scale:</label>
		<select 
			id="color-selector" 
			bind:value={selectedColorScale}
			class="py-1.5 px-3 rounded-md border-none bg-amber text-dark-bg font-bold cursor-pointer"
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

	<!-- Graph Container -->
	<div class="fixed bottom-5 left-5 w-[400px] h-[600px] bg-dark-surface/90 rounded-xl p-4 pt-12 shadow-lg z-[1000] backdrop-blur-sm">
		<select 
			bind:value={selectedGraphType} 
			class="absolute top-3 left-3 z-[1001] py-1.5 px-3 rounded-md bg-amber text-dark-bg border-none font-bold cursor-pointer"
		>
			<option value="summary">Statistics</option>
			<option value="histogram">Distribution</option>
			<option value="line">Temperatures</option>
			<option value="scatter">Latitude</option>
		</select>
		<canvas bind:this={chartElement} class="w-full h-full"></canvas>
	</div>

	<!-- Sidebar -->
	<div class="fixed top-0 right-0 w-[350px] h-screen bg-dark-surface/90 p-4 overflow-y-auto flex flex-col items-center backdrop-blur-md shadow-[-4px_0_10px_rgba(0,0,0,0.3)] z-[1000]">
		<h2 class="text-center mb-4 text-lg font-semibold text-white">
			Temperature Data for <span class="text-cyan">{featureId}</span>
		</h2>
		
		<!-- Unit Selector -->
		<div class="mt-2.5 flex gap-2.5 justify-center">
			<button 
				class="px-4 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 {currentUnit === 'Kelvin' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
				onclick={() => currentUnit = 'Kelvin'}
			>
				Kelvin
			</button>
			<button 
				class="px-4 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 {currentUnit === 'Celsius' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
				onclick={() => currentUnit = 'Celsius'}
			>
				Celsius
			</button>
			<button 
				class="px-4 py-2 border-none rounded-md font-bold cursor-pointer transition-colors duration-300 {currentUnit === 'Fahrenheit' ? 'bg-blue-600 text-white' : 'bg-amber text-dark-bg'}"
				onclick={() => currentUnit = 'Fahrenheit'}
			>
				Fahrenheit
			</button>
		</div>
		
		<!-- Temperature Table -->
		<div class="w-full mt-5 overflow-x-auto rounded-xl bg-white/5 shadow-[0_4px_15px_rgba(0,0,0,0.2)]">
			<table class="w-full text-white text-sm border-separate border-spacing-0 rounded-xl overflow-hidden">
				<thead>
					<tr>
						<th class="py-3 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Point</th>
						<th class="py-3 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">X</th>
						<th class="py-3 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Y</th>
						<th class="py-3 px-2 bg-amber/80 text-dark-bg font-semibold uppercase tracking-wider sticky top-0">Temp ({unitSymbol})</th>
					</tr>
				</thead>
				<tbody>
					{#each convertedTemperatureData.slice(0, 10) as point, i}
						<tr class="even:bg-white/[0.03] hover:bg-amber/15 transition-colors">
							<td class="py-2.5 px-2 border-b border-white/5 font-bold text-amber">{i + 1}</td>
							<td class="py-2.5 px-2 border-b border-white/5">{parseFloat(point.x || point.longitude || 0).toFixed(4)}</td>
							<td class="py-2.5 px-2 border-b border-white/5">{parseFloat(point.y || point.latitude || 0).toFixed(4)}</td>
							<td class="py-2.5 px-2 border-b border-white/5">{point.convertedTemp.toFixed(2)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<button 
				class="w-full bg-blue-500/80 hover:bg-blue-500 text-white border-none py-2 px-3 rounded-md font-bold cursor-pointer transition-colors duration-300 mt-2.5"
				onclick={() => goto(`/archive/${featureId}`)}
			>
				Download All Data
			</button>
		</div>
	</div>
</div>
