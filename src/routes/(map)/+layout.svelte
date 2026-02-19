<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
import { MapLibre, GeoJSONSource, FillLayer, LineLayer } from 'svelte-maplibre-gl';
import type { Map, MapMouseEvent, LngLatBoundsLike, FillLayerSpecification, FilterSpecification } from 'maplibre-gl';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import { Button } from '$lib/components/ui/button';
	import FeatureSidebar from '$lib/components/FeatureSidebar.svelte';
	import FeatureSearch from '$lib/components/FeatureSearch.svelte';
	import IntroCard from '$lib/components/IntroCard.svelte';
	import UserMenu from '$lib/components/UserMenu.svelte';
	import type { Snippet } from 'svelte';
	import XIcon from '@lucide/svelte/icons/x';

	let { children }: { children: Snippet } = $props();

	let map: Map | undefined = $state();
	let geojsonData: any = $state(null);
	let mapReady = $state(false);

	// Local UI state (not URL-driven)
	let selectedDate = $state('');
	let selectedColorScale: 'relative' | 'fixed' | 'gray' = $state('relative');
	let hoveredFeatureId: string | null = $state(null);
	let currentUnit: 'Kelvin' | 'Celsius' | 'Fahrenheit' = $state('Celsius');
	
	// Temperature filter state (in Kelvin)
	let tempFilterMin: number | null = $state(null);
	let tempFilterMax: number | null = $state(null);
	
	// Temperature hover tooltip
	let hoveredTemp: number | null = $state(null);
	let tooltipX = $state(0);
	let tooltipY = $state(0);

	// Temperature data (fetched here so map can use it for heatmap)
	// Use $state.raw to avoid deep reactive proxies over thousands of GeoJSON coordinates
	let heatmapGeojson: { type: 'FeatureCollection'; features: any[] } | null = $state.raw(null);
	let squareGeojson: { type: 'FeatureCollection'; features: any[] } | null = $state.raw(null);
	let relativeMin = $state(0);
	let relativeMax = $state(0);
	let avgTemp = $state(0);
	let histogramData: Array<{ range: string; count: number }> = $state([]);
	let waterOff = $state(false);
	const globalMin = 273.15;
	const globalMax = 308.15;

	// Default map view (MapLibre uses [lng, lat])
	const defaultCenter: [number, number] = [112.5, 2.5];
	const defaultZoom = 6;

	// Saved map position (to restore when closing sidebar)
	let savedMapView: { center: [number, number]; zoom: number } | null = $state(null);

	// URL is the single source of truth
	let urlFeatureId = $derived($page.params.id ?? null);
	let urlDate = $derived($page.url.searchParams.get('date') ?? '');

	// Derive selected feature FROM the URL
	let selectedFeature = $derived.by(() => {
		if (!urlFeatureId || !geojsonData) return null;

		const feature = geojsonData.features.find((f: any) => {
			const loc = f.properties.location || 'lake';
			const id = loc === 'lake' ? f.properties.name : `${f.properties.name}/${loc}`;
			return id === urlFeatureId;
		});

		if (!feature) return null;

		const name = feature.properties.name;
		const location = feature.properties.location || 'lake';

		// Calculate bounds from geometry
		const coords = feature.geometry.coordinates[0];
		const lngs = coords.map((c: number[]) => c[0]);
		const lats = coords.map((c: number[]) => c[1]);
		const bounds: LngLatBoundsLike = [
			[Math.min(...lngs), Math.min(...lats)],
			[Math.max(...lngs), Math.max(...lats)]
		];

		return { id: urlFeatureId, name, location, bounds };
	});

	// Sidebar is open when there's a selected feature
	let sidebarOpen = $derived(!!selectedFeature);

	// Track previous feature ID to detect transitions
	let previousFeatureId: string | null = null;
	let isInitialNavigation = true;

	// Effect handles map zoom as a SIDE EFFECT of state changes
	$effect(() => {
		const currentFeatureId = selectedFeature?.id ?? null;
		const bounds = selectedFeature?.bounds;

		// Read map and savedMapView without creating dependencies
		const currentMap = untrack(() => map);
		const currentSavedView = untrack(() => savedMapView);

		// Don't update previousFeatureId when map isn't ready — so when we landed
		// on /feature/<id> directly, we still run "Opening" (fitBounds) once the map loads.
		if (!mapReady || !currentMap) {
			return;
		}

		if (currentFeatureId && !previousFeatureId) {
			// Opening: save view, zoom to feature
			const center = currentMap.getCenter();
			savedMapView = {
				center: [center.lng, center.lat],
				zoom: currentMap.getZoom()
			};
			if (bounds) {
				// Skip animation on initial page load (just jump to the feature)
				const animate = !isInitialNavigation;
				currentMap.fitBounds(bounds, { padding: 20, animate });
			}
			isInitialNavigation = false;
			// Don't clear selectedDate/selectedColorScale here — sidebar sets them when it
			// runs loadDates(). Clearing here would overwrite the date on direct navigation
			// when the map becomes ready after the sidebar has already loaded.
		} else if (!currentFeatureId && previousFeatureId) {
			// Closing: restore view
			if (currentSavedView) {
				currentMap.easeTo({
					center: currentSavedView.center,
					zoom: currentSavedView.zoom
				});
			}
			savedMapView = null;
			// Reset local UI state
			selectedDate = '';
			selectedColorScale = 'relative';
			heatmapGeojson = null;
			squareGeojson = null;
			relativeMin = 0;
			relativeMax = 0;
			avgTemp = 0;
			histogramData = [];
			tempFilterMin = null;
			tempFilterMax = null;
		} else if (currentFeatureId && previousFeatureId && currentFeatureId !== previousFeatureId) {
			// Switching features: just zoom to new feature
			if (bounds) {
				currentMap.fitBounds(bounds, { padding: 20 });
			}
			// Reset local UI state
			selectedDate = '';
			selectedColorScale = 'relative';
			heatmapGeojson = null;
			squareGeojson = null;
			relativeMin = 0;
			relativeMax = 0;
			avgTemp = 0;
			histogramData = [];
			tempFilterMin = null;
			tempFilterMax = null;
		}

		previousFeatureId = currentFeatureId;
	});


	// Fill paint properties based on color scale - colors each square by its temperature
	let fillPaint = $derived.by(() => {
		let minTemp = selectedColorScale === 'relative' ? relativeMin : globalMin;
		let maxTemp = selectedColorScale === 'relative' ? relativeMax : globalMax;

		// Ensure valid range for interpolation
		if (minTemp >= maxTemp) {
			minTemp = globalMin;
			maxTemp = globalMax;
		}

		// Color ramp based on scale type - interpolates temperature to color
		const colorExpr = selectedColorScale === 'gray'
			? [
				'interpolate',
				['linear'],
				['get', 'temperature'],
				minTemp, 'rgb(40,40,40)',
				maxTemp, 'rgb(255,255,255)'
			]
			: [
				'interpolate',
				['linear'],
				['get', 'temperature'],
				minTemp, 'rgb(0,0,255)',
				minTemp + (maxTemp - minTemp) * 0.25, 'rgb(0,255,255)',
				minTemp + (maxTemp - minTemp) * 0.5, 'rgb(0,255,0)',
				minTemp + (maxTemp - minTemp) * 0.75, 'rgb(255,255,0)',
				maxTemp, 'rgb(255,0,0)'
			];

		return {
			'fill-color': colorExpr,
			'fill-opacity': 0.8
		} as unknown as FillLayerSpecification['paint'];
	});

	// MapLibre style with Esri World Imagery tiles
	const mapStyle = {
		version: 8 as const,
		sources: {
			'esri-imagery': {
				type: 'raster' as const,
				tiles: [
					'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
				],
				tileSize: 256,
				attribution:
					'Tiles &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
				maxzoom: 18
			}
		},
		layers: [
			{
				id: 'esri-imagery-layer',
				type: 'raster' as const,
				source: 'esri-imagery'
			}
		]
	};

	// All user interactions just change the URL
	function handleMapClick(e: MapMouseEvent) {
		if (!map) return;
		if (!map.getLayer('polygons-fill')) return;

		const features = map.queryRenderedFeatures(e.point, { layers: ['polygons-fill'] });

		if (features && features.length > 0) {
			const feature = features[0];
			const loc = feature.properties?.location || 'lake';
			const featureId =
				loc === 'lake' ? feature.properties?.name : `${feature.properties?.name}/${loc}`;

			// Navigate to feature (URL change will trigger state updates)
			goto(`/feature/${encodeURIComponent(featureId)}`, {
				replaceState: false,
				keepFocus: true,
				noScroll: true
			});
		} else if (selectedFeature) {
			// Navigate to home (URL change will trigger state updates)
			goto('/', { replaceState: false, keepFocus: true, noScroll: true });
		}
	}

	function handleMouseMove(e: MapMouseEvent) {
		if (!map) return;
		
		// Check temperature layer first
		if (map.getLayer('temperature-layer')) {
			const tempFeatures = map.queryRenderedFeatures(e.point, { layers: ['temperature-layer'] });
			if (tempFeatures && tempFeatures.length > 0) {
				const temp = tempFeatures[0].properties?.temperature;
				if (temp != null) {
					hoveredTemp = temp;
					tooltipX = e.point.x;
					tooltipY = e.point.y;
					map.getCanvas().style.cursor = 'crosshair';
					return;
				}
			}
		}
		hoveredTemp = null;
		
		// Check polygon layer
		if (!map.getLayer('polygons-fill')) return;

		const features = map.queryRenderedFeatures(e.point, { layers: ['polygons-fill'] });

		if (features && features.length > 0) {
			const loc = features[0].properties?.location || 'lake';
			hoveredFeatureId =
				loc === 'lake'
					? features[0].properties?.name
					: `${features[0].properties?.name}/${loc}`;
			map.getCanvas().style.cursor = 'pointer';
		} else {
			hoveredFeatureId = null;
			map.getCanvas().style.cursor = '';
		}
	}

	async function loadTemperatureData(featureId: string, date: string) {
		// Clear previous data first
		heatmapGeojson = null;
		squareGeojson = null;
		relativeMin = 0;
		relativeMax = 0;
		avgTemp = 0;
		histogramData = [];
		waterOff = false;

		if (!featureId || !date) return;

		try {
			const response = await fetch(`/api/feature/${featureId}/temperature/${date}`);
			if (!response.ok) return;

			const data = (await response.json()) as {
				error?: string;
				geojson?: { type: 'FeatureCollection'; features: any[] };
				min_max?: [number, number];
				histogram?: Array<{ range: string; count: number }>;
				avg?: number;
				wtoff?: boolean;
			};
			if (data.error || !data.geojson) return;

			// Server returns ready-to-use GeoJSON and pre-computed stats
			heatmapGeojson = data.geojson;
			squareGeojson = data.geojson.features.length > 0 ? pointsToSquares(data.geojson) : null;
			relativeMin = data.min_max?.[0] || 0;
			relativeMax = data.min_max?.[1] || 0;
			avgTemp = data.avg || 0;
			histogramData = data.histogram || [];
			waterOff = data.wtoff || false;
		} catch (err) {
			console.error('Error loading temperature data:', err);
		}
	}

	function handleDateChange(event: CustomEvent<string>) {
		selectedDate = event.detail;
		if (selectedFeature) {
			loadTemperatureData(selectedFeature.id, event.detail);
		}
	}

	function handleColorScaleChange(event: CustomEvent<'relative' | 'fixed' | 'gray'>) {
		selectedColorScale = event.detail;
	}

	function handleTempFilterChange(event: CustomEvent<{ min: number | null; max: number | null }>) {
		tempFilterMin = event.detail.min;
		tempFilterMax = event.detail.max;
	}

	// MapLibre filter expression for temperature filtering (GPU-accelerated)
	let tempLayerFilter = $derived.by((): FilterSpecification | undefined => {
		if (tempFilterMin === null || tempFilterMax === null) {
			return undefined; // No filter - show all points
		}
		return [
			'all',
			['>=', ['get', 'temperature'], tempFilterMin],
			['<=', ['get', 'temperature'], tempFilterMax]
		] as unknown as FilterSpecification;
	});

	function handleSidebarClose() {
		// Just change the URL - state will update automatically
		goto('/', { replaceState: false, keepFocus: true, noScroll: true });
	}

	function handleMapLoad() {
		mapReady = true;
	}

	onMount(async () => {
		try {
			const response = await fetch('/api/polygons');
			geojsonData = await response.json();
		} catch (err) {
			console.error('Error loading polygons:', err);
		}
	});

	// Helper to get feature ID for expressions
	function getFeatureExpression(featureId: string | null | undefined): string {
		return featureId ?? '';
	}

	// Imperatively update polygon styling when selection/hover changes,
	// as a safeguard in case the library's paint prop tracking misses updates
	$effect(() => {
		const selectedName = selectedFeature?.name ?? '';
		const hoveredName = hoveredFeatureId?.split('/')[0] ?? '';

		if (!map || !mapReady) return;
		if (!map.getLayer('polygons-fill')) return;

		map.setPaintProperty('polygons-fill', 'fill-color', [
			'case',
			['==', ['get', 'name'], selectedName],
			'#00ff00',
			['==', ['get', 'name'], hoveredName],
			'#00ff00',
			'transparent'
		]);
		map.setPaintProperty('polygons-line', 'line-color', [
			'case',
			['==', ['get', 'name'], selectedName],
			'#00ff00',
			['==', ['get', 'name'], hoveredName],
			'#00ff00',
			'#8abbff'
		]);
		map.setPaintProperty('polygons-line', 'line-width', [
			'case',
			['==', ['get', 'name'], selectedName],
			3,
			2
		]);
		map.setPaintProperty('polygons-line', 'line-opacity', [
			'case',
			['==', ['get', 'name'], selectedName],
			0.3,
			1
		]);
	});
	
	/**
	 * Detect the grid cell spacing from a set of points by finding the median gap
	 * in sorted unique x and y coordinates.
	 */
	function detectGridSpacing(features: any[]): { dx: number; dy: number } {
		const lngs = new Set<number>();
		const lats = new Set<number>();
		for (const f of features) {
			const [lng, lat] = f.geometry.coordinates;
			lngs.add(lng);
			lats.add(lat);
		}

		function medianGap(values: Set<number>): number {
			const sorted = [...values].sort((a, b) => a - b);
			if (sorted.length < 2) return 0.0007; // fallback ~70m
			const gaps: number[] = [];
			for (let i = 1; i < sorted.length; i++) {
				const g = sorted[i] - sorted[i - 1];
				if (g > 1e-8) gaps.push(g);
			}
			if (gaps.length === 0) return 0.0007;
			gaps.sort((a, b) => a - b);
			return gaps[Math.floor(gaps.length / 2)];
		}

		return { dx: medianGap(lngs), dy: medianGap(lats) };
	}

	/**
	 * Convert a Point FeatureCollection to a Polygon FeatureCollection
	 * where each point becomes a square cell for contiguous rendering.
	 */
	function pointsToSquares(
		geojson: { type: 'FeatureCollection'; features: any[] }
	): { type: 'FeatureCollection'; features: any[] } {
		const { dx, dy } = detectGridSpacing(geojson.features);
		const halfDx = dx / 2;
		const halfDy = dy / 2;

		return {
			type: 'FeatureCollection',
			features: geojson.features.map((f) => {
				const [lng, lat] = f.geometry.coordinates;
				return {
					type: 'Feature',
					geometry: {
						type: 'Polygon',
						coordinates: [[
							[lng - halfDx, lat - halfDy],
							[lng + halfDx, lat - halfDy],
							[lng + halfDx, lat + halfDy],
							[lng - halfDx, lat + halfDy],
							[lng - halfDx, lat - halfDy]
						]]
					},
					properties: f.properties
				};
			})
		};
	}

	// Format temperature for tooltip based on selected unit
	function convertTemp(kelvin: number): number {
		if (currentUnit === 'Celsius') return kelvin - 273.15;
		if (currentUnit === 'Fahrenheit') return (kelvin - 273.15) * 9 / 5 + 32;
		return kelvin;
	}
	
	let unitSymbol = $derived.by(() => {
		if (currentUnit === 'Kelvin') return 'K';
		if (currentUnit === 'Celsius') return '°C';
		return '°F';
	});
	
	let tooltipTempDisplay = $derived(
		hoveredTemp != null ? convertTemp(hoveredTemp).toFixed(1) + unitSymbol : ''
	);
</script>

<svelte:head>
	<title>Satellite Water Temperature Monitoring</title>
</svelte:head>

<Sidebar.Provider open={sidebarOpen} onOpenChange={(open) => { if (!open) handleSidebarClose(); }}>
	<div class="flex h-screen w-full">
		<!-- Feature Sidebar (left side) – only in DOM when a feature is selected -->
		{#if selectedFeature}
			<Sidebar.Sidebar side="left" collapsible="offcanvas" class="border-r w-full sm:max-w-md">
				<Sidebar.Header class="flex flex-row items-center justify-between gap-2 px-4 py-3 border-b shrink-0 bg-background">
					<span class="font-semibold text-foreground truncate">
						{selectedFeature.name ?? selectedFeature.id ?? 'Water body'}
					</span>
					<Button variant="ghost" size="icon-sm" onclick={handleSidebarClose} class="shrink-0">
						<XIcon class="size-4" />
						<span class="sr-only">Close</span>
					</Button>
				</Sidebar.Header>
				<Sidebar.Content class="flex flex-col min-h-0 bg-background">
					<FeatureSidebar
						featureId={selectedFeature.id}
						featureName={selectedFeature.name ?? ''}
						isOpen={true}
						initialDate={urlDate}
						bind:selectedDate
						bind:selectedColorScale
						bind:currentUnit
						{relativeMin}
						{relativeMax}
						{avgTemp}
						{histogramData}
						{waterOff}
						on:close={handleSidebarClose}
						on:dateChange={handleDateChange}
						on:colorScaleChange={handleColorScaleChange}
						on:tempFilterChange={handleTempFilterChange}
					/>
				</Sidebar.Content>
			</Sidebar.Sidebar>
		{/if}

		<!-- Main content (map + footer) -->
		<main class="flex-1 flex flex-col min-w-0">
			<!-- Map Container -->
			<div class="flex-1 relative w-full">
				<MapLibre
					bind:map
					class="h-full w-full"
					style={mapStyle}
					center={defaultCenter}
					zoom={defaultZoom}
					minZoom={2}
					maxZoom={19}
					onclick={handleMapClick}
					onmousemove={handleMouseMove}
					onload={handleMapLoad}
				>
					{#if geojsonData}
						<!-- GeoJSON Source for polygons -->
						<GeoJSONSource id="polygons" data={geojsonData}>
							<!-- Fill layer for hover/selection detection -->
							<FillLayer
								id="polygons-fill"
								paint={{
									'fill-color': [
										'case',
										['==', ['get', 'name'], getFeatureExpression(selectedFeature?.name)],
										'#00ff00',
										['==', ['get', 'name'], getFeatureExpression(hoveredFeatureId?.split('/')[0])],
										'#00ff00',
										'transparent'
									],
									'fill-opacity': 0.1
								}}
							/>
							<!-- Line layer for borders -->
							<LineLayer
								id="polygons-line"
								paint={{
									'line-color': [
										'case',
										['==', ['get', 'name'], getFeatureExpression(selectedFeature?.name)],
										'#00ff00',
										['==', ['get', 'name'], getFeatureExpression(hoveredFeatureId?.split('/')[0])],
										'#00ff00',
										'#8abbff'
									],
									'line-width': [
										'case',
										['==', ['get', 'name'], getFeatureExpression(selectedFeature?.name)],
										3,
										2
									],
									'line-opacity': [
										'case',
										['==', ['get', 'name'], getFeatureExpression(selectedFeature?.name)],
										0.3,
										1
									]
								}}
							/>
						</GeoJSONSource>
					{/if}

					{#if squareGeojson}
						<!-- Temperature squares - each colored by its temperature value -->
						{#key selectedDate}
							<GeoJSONSource id="temperature-points" data={squareGeojson}>
								<FillLayer
									id="temperature-layer"
									paint={fillPaint}
									filter={tempLayerFilter}
								/>
							</GeoJSONSource>
						{/key}
					{/if}
				</MapLibre>
				<!-- Floating search bar (top left) -->
				{#if !sidebarOpen}
					<FeatureSearch {geojsonData} />
				{/if}
				<!-- Floating intro card (bottom left) -->
				<IntroCard />
				<!-- Floating user menu (top right) -->
				<UserMenu />

				<!-- Temperature hover tooltip (styled like shadcn tooltip) -->
				{#if hoveredTemp != null}
					<div 
						class="absolute pointer-events-none z-50 px-3 py-1.5 text-xs font-medium bg-foreground text-background rounded-md shadow-md"
						style="left: {tooltipX + 12}px; top: {tooltipY - 12}px;"
					>
						{tooltipTempDisplay}
					</div>
				{/if}
			</div>

		</main>
	</div>

	<!-- Hidden slot for child pages (they don't render anything) -->
	<div class="hidden">
		{@render children()}
	</div>
</Sidebar.Provider>
