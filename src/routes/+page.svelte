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
							const name = feature.properties.name;
							const location = feature.properties.location || 'lake';
							// Lakes use just name, rivers use name/location
							const featureId = location === 'lake' ? name : `${name}/${location}`;
							if (name) {
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
</svelte:head>

<div class="min-h-screen bg-dark-bg font-poppins text-white">
	<!-- Hero Section -->
	<div class="relative bg-gradient-to-r from-[#0b3d91] to-cyan py-12 px-5 text-center">
		<h1 class="m-0 text-3xl md:text-4xl lg:text-5xl font-bold drop-shadow-[3px_3px_6px_rgba(0,0,0,0.6)]">
			Real-Time Global Lake Temperature Analysis
		</h1>
	</div>

	<!-- Map Container -->
	<div class="relative w-full h-[90vh] bg-dark-card border-t-4 border-cyan -mt-8">
		<h3 class="text-center text-xl md:text-2xl uppercase font-bold py-4 text-white">
			Satellite Map
		</h3>
		<div bind:this={mapElement} class="h-[calc(100%-60px)] w-full rounded-lg"></div>
	</div>

	<!-- Footer -->
	<footer class="bg-dark-surface text-white py-5 text-center text-sm mt-5">
		<p>&copy; 2025 Satellite Water Temperature Monitoring. All rights reserved.</p>
		<a 
			href="/admin/jobs" 
			class="text-cyan hover:text-white transition-colors duration-300 mt-2 inline-block font-medium"
		>
			Admin Dashboard
		</a>
	</footer>
</div>
