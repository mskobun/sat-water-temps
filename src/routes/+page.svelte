<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let mapElement: HTMLDivElement;
	let map: any;

	onMount(async () => {
		// Dynamically import Leaflet to avoid SSR issues
		const L = await import('leaflet');

		map = L.map(mapElement, {
			center: [2.5, 112.5],
			zoom: 6,
			minZoom: 2,
			maxZoom: 19
		});

		L.tileLayer(
			'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
			{
				attribution:
					'Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
				maxZoom: 19
			}
		).addTo(map);

		// Load GeoJSON features
		try {
			const response = await fetch('/api/polygons');
			const data = await response.json();

			L.geoJSON(data, {
				style: () => ({ color: '#8abbff', weight: 2 }),
				onEachFeature: (feature: any, layer: any) => {
					layer.on({
						mouseover: () => layer.setStyle({ color: '#00ff00' }),
						mouseout: () => layer.setStyle({ color: '#8abbff' }),
						click: () => {
							const featureId = feature.properties.name;
							if (featureId) {
								goto(`/feature/${featureId}`);
							}
						}
					});
				}
			}).addTo(map);
		} catch (err) {
			console.error('Error loading polygons:', err);
		}
	});
</script>

<svelte:head>
	<title>Satellite Water Temperature Monitoring</title>
	<link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
	<link
		href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap"
		rel="stylesheet"
	/>
</svelte:head>

<div class="hero">
	<h1>Real-Time Global Lake Temperature Analysis</h1>
</div>

<div class="map-container">
	<h3>Satellite Map</h3>
	<div bind:this={mapElement} id="map"></div>
</div>

<footer>
	&copy; 2025 Satellite Water Temperature Monitoring. All rights reserved.
	<br />
	<a href="/admin/jobs" style="color: #48c6ef; margin-top: 10px; display: inline-block;">
		Admin Dashboard
	</a>
</footer>

<style>
	:global(body) {
		font-family: 'Poppins', sans-serif;
		margin: 0;
		padding: 0;
		background: #121212;
		color: #fff;
		transition: all 0.3s ease-in-out;
	}

	.hero {
		text-align: center;
		padding: 50px 20px;
		background: linear-gradient(to right, #0b3d91, #48c6ef);
		color: #fff;
		font-size: 40px;
		font-weight: 700;
	}

	.hero h1 {
		margin: 0;
		text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.6);
	}

	.map-container {
		text-align: center;
		padding: 20px;
		background: #222;
		margin: 0;
		width: 100vw;
		height: 90vh;
		border-radius: 0;
		box-shadow: none;
		position: relative;
		border-top: 5px solid #48c6ef;
		margin-top: -40px;
	}

	.map-container h3 {
		font-size: 28px;
		margin-bottom: 10px;
		color: #fff;
		text-transform: uppercase;
		font-weight: 700;
	}

	#map {
		height: 100%;
		width: 100%;
		border-radius: 10px;
	}

	footer {
		background-color: #1e1e1e;
		color: white;
		padding: 20px;
		text-align: center;
		font-size: 14px;
		margin-top: 20px;
	}
</style>

