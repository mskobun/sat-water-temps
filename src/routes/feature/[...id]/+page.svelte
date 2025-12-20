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
	function convertTemp(kelvin: number): number {
		if (currentUnit === 'Celsius') return kelvin - 273.15;
		if (currentUnit === 'Fahrenheit') return (kelvin - 273.15) * 9/5 + 32;
		return kelvin;
	}
	
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
		const convertedTemps = temps.map(t => convertTemp(t));
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

<div class="feature-page-wrapper">
	<div id="map-container">
		<div bind:this={mapElement} id="map"></div>
		<button id="back-btn" on:click={() => goto('/')}>Back</button>
	</div>

<div id="date-selector-container">
	<label for="date-selector">Select Date:</label>
	<select id="date-selector" bind:value={selectedDate}>
		{#each dates as date}
			<option value={date}>{formatDateTime(date)}</option>
		{/each}
	</select>
</div>

{#if showWaterOffAlert}
	<div id="mask-alert-container">
		<p>Water Mask is off!</p>
	</div>
{/if}

<div id="color-selector-container">
	<label for="color-selector">Color Scale:</label>
	<select id="color-selector" bind:value={selectedColorScale}>
		<option value="relative">Relative</option>
		<option value="fixed">Fixed</option>
		<option value="gray">Grayscale</option>
	</select>
	<div id="color-scale-preview" class:gray={selectedColorScale === 'gray'}>
		<span class="temp-min-max" id="min-label">
			{selectedColorScale === 'relative' ? convertTemp(relativeMin).toFixed(2) : convertTemp(globalMin).toFixed(2)}
		</span>
		<span class="temp-min-max" id="unit-label">{unitSymbol}</span>
		<span class="temp-min-max" id="max-label">
			{selectedColorScale === 'relative' ? convertTemp(relativeMax).toFixed(2) : convertTemp(globalMax).toFixed(2)}
		</span>
	</div>
</div>

<div id="graph-container">
	<select bind:value={selectedGraphType} class="graph-type-selector">
		<option value="summary">Statistics</option>
		<option value="histogram">Distribution</option>
		<option value="line">Temperatures</option>
		<option value="scatter">Latitude</option>
	</select>
	<canvas bind:this={chartElement} id="temperatureChart"></canvas>
</div>

<div id="sidebar">
	<h2>Temperature Data for <span>{featureId}</span></h2>
	
	<div class="unit-selector">
		<button class:active={currentUnit === 'Kelvin'} on:click={() => currentUnit = 'Kelvin'}>Kelvin</button>
		<button class:active={currentUnit === 'Celsius'} on:click={() => currentUnit = 'Celsius'}>Celsius</button>
		<button class:active={currentUnit === 'Fahrenheit'} on:click={() => currentUnit = 'Fahrenheit'}>Fahrenheit</button>
	</div>
	
	<div id="temperature-boxes">
		<table>
			<thead>
				<tr>
					<th>Point</th>
					<th>X</th>
					<th>Y</th>
					<th>Temp ({unitSymbol})</th>
				</tr>
			</thead>
			<tbody>
				{#each temperatureData.slice(0, 10) as point, i}
					<tr>
						<td>{i + 1}</td>
						<td>{parseFloat(point.x || point.longitude || 0).toFixed(4)}</td>
						<td>{parseFloat(point.y || point.latitude || 0).toFixed(4)}</td>
						<td>{convertTemp(parseFloat(point.LST_filter || point.temperature || 0)).toFixed(2)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<button class="view-all-btn" on:click={() => goto(`/archive/${featureId}`)}>
			Download All Data
		</button>
	</div>
</div>
</div>

<style>
	.feature-page-wrapper {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		display: flex;
		height: 100vh;
		width: 100vw;
		overflow: hidden;
		background-color: #121212;
		z-index: 1;
		opacity: 0;
		transform: scale(0.9);
		animation: fadeIn 0.5s forwards ease-out;
	}
	
	@keyframes fadeIn {
		to {
			opacity: 1;
			transform: scale(1);
		}
	}
	
	#map-container {
		flex: 3;
		position: relative;
	}
	
	#map {
		width: 100%;
		height: 100vh;
		filter: brightness(90%);
	}
	
	#sidebar {
		position: fixed;
		top: 0;
		right: 0;
		width: 350px;
		height: 100vh;
		background: rgba(30, 30, 30, 0.9);
		padding: 15px;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		align-items: center;
		backdrop-filter: blur(10px);
		box-shadow: -4px 0 10px rgba(0, 0, 0, 0.3);
		z-index: 1000;
	}
	
	h2 {
		text-align: center;
		margin-bottom: 15px;
		font-size: 18px;
		font-weight: 600;
	}
	
	#back-btn {
		position: absolute;
		top: 20px;
		left: 20px;
		background-color: #007BFF;
		color: #fff;
		padding: 10px 20px;
		border: none;
		border-radius: 5px;
		cursor: pointer;
		font-size: 16px;
		font-weight: bold;
		transition: background-color 0.3s;
		z-index: 1000;
	}
	
	#back-btn:hover {
		background-color: #0056b3;
	}
	
	#date-selector-container {
		position: absolute;
		top: 20px;
		left: 50%;
		transform: translateX(-50%);
		background: rgba(30, 30, 30, 0.9);
		padding: 10px;
		border-radius: 8px;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
		z-index: 999;
	}
	
	#date-selector, #color-selector {
		padding: 5px;
		border-radius: 5px;
		border: none;
		background: #f9a44a;
		color: #121212;
		font-weight: bold;
		cursor: pointer;
	}
	
	#mask-alert-container {
		position: absolute;
		top: 70px;
		left: 50%;
		transform: translateX(-50%);
		background-color: #f44336;
		color: #fff;
		padding: 10px 20px;
		border-radius: 5px;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
		z-index: 1001;
	}
	
	#color-selector-container {
		position: absolute;
		top: 20px;
		left: 70%;
		transform: translateX(-30%);
		background: rgba(30, 30, 30, 0.9);
		padding: 10px;
		border-radius: 8px;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
		z-index: 999;
	}
	
	#color-scale-preview {
		margin-top: 10px;
		width: 100%;
		height: 20px;
		border-radius: 5px;
		background: linear-gradient(to right, #000080, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000, #800000);
		position: relative;
	}
	
	#color-scale-preview.gray {
		background: linear-gradient(to right, #000, #fff);
	}
	
	.temp-min-max {
		position: absolute;
		top: 25px;
		font-size: 12px;
		color: white;
	}
	
	#min-label { left: 0; }
	#max-label { right: 0; }
	#unit-label { left: 50%; transform: translateX(-50%); }
	
	.unit-selector {
		margin-top: 10px;
		display: flex;
		gap: 10px;
		justify-content: center;
	}
	
	.unit-selector button {
		padding: 8px 16px;
		border: none;
		border-radius: 5px;
		background-color: #f9a44a;
		color: #121212;
		font-weight: bold;
		cursor: pointer;
		transition: background-color 0.3s;
	}
	
	.unit-selector button.active {
		background-color: #007BFF;
		color: #fff;
	}
	
	#temperature-boxes {
		width: 100%;
		margin-top: 20px;
		overflow-x: auto;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.05);
		box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
	}
	
	table {
		width: 100%;
		color: white;
		border-collapse: separate;
		border-spacing: 0;
		font-size: 13px;
		border-radius: 10px;
		overflow: hidden;
	}
	
	th {
		padding: 12px 8px;
		background: rgba(249, 164, 74, 0.8);
		color: #121212;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		position: sticky;
		top: 0;
	}
	
	td {
		padding: 10px 8px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	}
	
	tr:nth-child(even) {
		background-color: rgba(255, 255, 255, 0.03);
	}
	
	tr:hover {
		background-color: rgba(249, 164, 74, 0.15);
	}
	
	td:first-child {
		font-weight: bold;
		color: #f9a44a;
	}
	
	.view-all-btn {
		background: rgba(66, 135, 245, 0.8);
		color: white;
		border: none;
		padding: 8px 12px;
		border-radius: 5px;
		font-weight: bold;
		cursor: pointer;
		transition: background 0.3s;
		margin-top: 10px;
		width: 100%;
	}
	
	.view-all-btn:hover {
		background: rgba(66, 135, 245, 1);
	}
	
	#graph-container {
		position: fixed;
		bottom: 20px;
		left: 20px;
		width: 400px;
		height: 600px;
		background: rgba(30, 30, 30, 0.9);
		border-radius: 10px;
		padding: 15px;
		padding-top: 40px;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
		z-index: 1000;
		overflow: visible;
	}
	
	.graph-type-selector {
		position: absolute;
		top: 10px;
		left: 10px;
		z-index: 1001;
		padding: 5px;
		border-radius: 5px;
		background: #f9a44a;
		color: #121212;
		border: none;
		font-weight: bold;
		cursor: pointer;
	}
	
	#temperatureChart {
		width: 100%;
		height: 100%;
	}
</style>
