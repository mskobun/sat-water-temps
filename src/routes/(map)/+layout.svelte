<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import FeatureSidebar from '$lib/components/FeatureSidebar.svelte';

	let mapElement: HTMLDivElement;
	let map: any;
	let L: any;
	let geojsonLayer: any;
	let geojsonData: any = null;
	let layersByFeatureId: Map<string, any> = new Map();
	let currentOverlay: any = null;
	let currentPolygon: any = null;
	let mapReady = false;
	
	// Selected feature state
	let selectedFeature: { id: string; name: string; location: string; bounds: any } | null = null;
	let sidebarOpen = false;
	let selectedDate = '';
	let selectedColorScale: 'relative' | 'fixed' | 'gray' = 'relative';
	
	// Default map view
	const defaultCenter: [number, number] = [2.5, 112.5];
	const defaultZoom = 6;
	
	// Saved map position (to restore when closing sidebar)
	let savedMapView: { center: [number, number]; zoom: number } | null = null;
	let isProgrammaticMove = false; // Flag to ignore programmatic map movements
	
	// Get feature ID from URL path params (e.g., /feature/Magat or /feature/Magat/river)
	$: urlFeatureId = $page.params.id ? $page.params.id : null;
	
	// React to URL changes
	$: if (mapReady) {
		handleUrlChange(urlFeatureId);
	}
	
	function handleUrlChange(featureId: string | null) {
		if (featureId) {
			// Select feature if different from current
			if (selectedFeature?.id !== featureId) {
				selectFeatureById(featureId);
			}
		} else if (selectedFeature) {
			// Clear selection if URL has no feature
			clearSelection(false);
		}
	}
	
	// Update URL when feature changes
	function updateUrl(featureId: string | null) {
		if (featureId) {
			goto(`/feature/${encodeURIComponent(featureId)}`, { replaceState: false, keepFocus: true, noScroll: true });
		} else {
			goto('/', { replaceState: false, keepFocus: true, noScroll: true });
		}
	}
	
	// Select feature by ID (for URL navigation)
	function selectFeatureById(featureId: string) {
		if (!geojsonData || !layersByFeatureId.has(featureId)) return false;
		
		const layer = layersByFeatureId.get(featureId);
		const feature = geojsonData.features.find((f: any) => {
			const loc = f.properties.location || 'lake';
			const id = loc === 'lake' ? f.properties.name : `${f.properties.name}/${loc}`;
			return id === featureId;
		});
		
		if (feature && layer) {
			selectFeatureInternal(feature, layer, false);
			return true;
		}
		return false;
	}

	function clearSelection(shouldUpdateUrl = true) {
		sidebarOpen = false;
		selectedFeature = null;
		selectedDate = '';
		selectedColorScale = 'relative';
		
		// Remove overlay
		if (currentOverlay && map) {
			map.removeLayer(currentOverlay);
			currentOverlay = null;
		}
		
		// Remove polygon highlight
		if (currentPolygon && map) {
			map.removeLayer(currentPolygon);
			currentPolygon = null;
		}
		
		// Reset layer styles
		if (geojsonLayer) {
			geojsonLayer.setStyle({ color: '#8abbff', weight: 2 });
		}
		
		// Restore saved map view if available
		if (savedMapView && map) {
			isProgrammaticMove = true;
			map.setView(savedMapView.center, savedMapView.zoom);
			savedMapView = null;
		}
		
		// Update URL
		if (shouldUpdateUrl) {
			updateUrl(null);
		}
	}

	// Internal select function that optionally updates URL
	function selectFeatureInternal(feature: any, layer: any, shouldUpdateUrl = true) {
		const name = feature.properties.name;
		const location = feature.properties.location || 'lake';
		const featureId = location === 'lake' ? name : `${name}/${location}`;
		
		if (!name) return;
		
		// If clicking the same feature, do nothing
		if (selectedFeature?.id === featureId) return;
		
		// Remove previous overlay and polygon
		if (currentOverlay) {
			map.removeLayer(currentOverlay);
			currentOverlay = null;
		}
		if (currentPolygon) {
			map.removeLayer(currentPolygon);
			currentPolygon = null;
		}
		
		// Reset all layer styles first
		geojsonLayer.setStyle({ color: '#8abbff', weight: 2 });
		
		// Get bounds from the layer
		const bounds = layer.getBounds();
		
		// Create polygon overlay for the selected feature
		const coords = feature.geometry.coordinates;
		if (Array.isArray(coords) && Array.isArray(coords[0])) {
			const latLngs = coords[0].map((coord: number[]) => [coord[1], coord[0]]);
			currentPolygon = L.polygon(latLngs, {
				color: '#00ff00',
				opacity: 0.3,
				weight: 3,
				fillOpacity: 0.1
			}).addTo(map);
		}
		
		// Set selected feature
		selectedFeature = { id: featureId, name, location, bounds };
		
		// Reset date/colorScale for new feature
		selectedDate = '';
		selectedColorScale = 'relative';
		
		// Save current map view before zooming (only if not already saved)
		if (!savedMapView) {
			savedMapView = {
				center: [map.getCenter().lat, map.getCenter().lng],
				zoom: map.getZoom()
			};
		}
		
		// Zoom to feature (mark as programmatic to avoid clearing saved view)
		isProgrammaticMove = true;
		map.fitBounds(bounds, { padding: [20, 20] });
		
		// Add initial overlay (will be updated when sidebar loads dates)
		updateOverlay();
		
		// Open sidebar
		sidebarOpen = true;
		
		// Update URL
		if (shouldUpdateUrl) {
			updateUrl(featureId);
		}
	}

	// Public select function called from map clicks
	function selectFeature(feature: any, layer: any) {
		selectFeatureInternal(feature, layer, true);
	}

	function updateOverlay() {
		if (!map || !selectedFeature || !currentPolygon) return;
		
		// Remove existing overlay
		if (currentOverlay) {
			map.removeLayer(currentOverlay);
		}
		
		// Build overlay URL
		const featureId = selectedFeature.id;
		let overlayUrl: string;
		
		if (selectedDate) {
			overlayUrl = `/api/feature/${featureId}/tif/${selectedDate}/${selectedColorScale}`;
		} else {
			// Use latest if no date selected
			overlayUrl = `/api/latest_lst_tif/${featureId}`;
		}
		
		// Add new overlay
		currentOverlay = L.imageOverlay(overlayUrl, currentPolygon.getBounds()).addTo(map);
	}

	function handleDateChange(event: CustomEvent<string>) {
		selectedDate = event.detail;
		updateOverlay();
	}

	function handleColorScaleChange(event: CustomEvent<'relative' | 'fixed' | 'gray'>) {
		selectedColorScale = event.detail;
		updateOverlay();
	}

	function handleSidebarClose() {
		clearSelection();
	}

	onMount(async () => {
		// Dynamically import Leaflet to avoid SSR issues
		L = await import('leaflet');

		map = L.map(mapElement, {
			center: defaultCenter,
			zoom: defaultZoom,
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

		// Map click handler - clear selection when clicking outside features
		map.on('click', () => {
			if (selectedFeature) {
				clearSelection();
			}
		});
		
		// Clear saved map view if user manually moves/zooms the map
		map.on('moveend', () => {
			if (isProgrammaticMove) {
				isProgrammaticMove = false;
				return;
			}
			// User moved the map manually - clear saved view
			if (savedMapView && selectedFeature) {
				savedMapView = null;
			}
		});

		// Load GeoJSON features
		try {
			const response = await fetch('/api/polygons');
			geojsonData = await response.json();

			geojsonLayer = L.geoJSON(geojsonData, {
				style: () => ({ color: '#8abbff', weight: 2 }),
				onEachFeature: (feature: any, layer: any) => {
					// Store layer reference by feature ID
					const loc = feature.properties.location || 'lake';
					const featureId = loc === 'lake' ? feature.properties.name : `${feature.properties.name}/${loc}`;
					layersByFeatureId.set(featureId, layer);
					
					layer.on({
						mouseover: () => {
							if (selectedFeature?.id !== featureId) {
								layer.setStyle({ color: '#00ff00' });
							}
						},
						mouseout: () => {
							if (selectedFeature?.id !== featureId) {
								layer.setStyle({ color: '#8abbff' });
							}
						},
						click: (e: any) => {
							// Stop propagation to prevent map click handler
							L.DomEvent.stopPropagation(e);
							selectFeature(feature, layer);
						}
					});
				}
			}).addTo(map);
			
			// Mark map as ready - this will trigger URL check via reactive statement
			mapReady = true;
		} catch (err) {
			console.error('Error loading polygons:', err);
		}
	});
</script>

<svelte:head>
	<title>Satellite Water Temperature Monitoring</title>
</svelte:head>

<div class="h-screen bg-dark-bg font-poppins text-white flex flex-col">
	<!-- Map Container -->
	<div class="flex-1 relative w-full">
		<div bind:this={mapElement} class="h-full w-full"></div>
	</div>

	<!-- Footer -->
	<footer class="bg-dark-surface text-white py-3 text-center text-sm">
		<p class="m-0">&copy; 2025 Satellite Water Temperature Monitoring. All rights reserved.</p>
		<a 
			href="/admin/jobs" 
			class="text-cyan hover:text-white transition-colors duration-300 mt-1 inline-block font-medium"
		>
			Admin Dashboard
		</a>
	</footer>
</div>

<!-- Feature Sidebar -->
<FeatureSidebar 
	featureId={selectedFeature?.id || ''}
	isOpen={sidebarOpen}
	bind:selectedDate
	bind:selectedColorScale
	on:close={handleSidebarClose}
	on:dateChange={handleDateChange}
	on:colorScaleChange={handleColorScaleChange}
/>

<!-- Hidden slot for child pages (they don't render anything) -->
<div class="hidden">
	<slot />
</div>
