<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { useSearchParams, createSearchParamsSchema } from 'runed/kit';
	import { MapLibre, GeoJSONSource, ImageSource, FillLayer, LineLayer, CircleLayer, RasterLayer } from 'svelte-maplibre-gl';
	import type {
		Map,
		MapMouseEvent,
		LngLatBoundsLike
	} from 'maplibre-gl';
	import * as Sidebar from '$lib/components/ui/sidebar';
	import * as Drawer from '$lib/components/ui/drawer';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import FeatureSidebar from '$lib/components/FeatureSidebar.svelte';
	import PointHistoryPanel from '$lib/components/PointHistoryPanel.svelte';
	import FeatureSearch from '$lib/components/FeatureSearch.svelte';
	import UserMenu from '$lib/components/UserMenu.svelte';
	import { IsMobile } from '$lib/hooks/is-mobile.svelte.js';
	import type { DeckTemperatureOverlay } from '$lib/deck-temperature-overlay';
	import type { AffineTransform } from '$lib/landsat-pixel-quads';
	import { fetchTemperatureMetadata } from '$lib/api';
	import { Kbd } from '$lib/components/ui/kbd';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { toast } from 'svelte-sonner';
	import type { Snippet } from 'svelte';
	import XIcon from '@lucide/svelte/icons/x';
	import ChevronUpIcon from '@lucide/svelte/icons/chevron-up';
	import HistoryIcon from '@lucide/svelte/icons/history';
	import CopyIcon from '@lucide/svelte/icons/copy';

	const isMobile = new IsMobile();
	const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform);
	const modKeyLabel = isMac ? '⌥' : 'Alt';
	type DuckDBCacheModule = typeof import('$lib/duckdb-cache');
	let duckdbCacheModulePromise: Promise<DuckDBCacheModule> | null = null;

	async function getDuckDBCacheModule(): Promise<DuckDBCacheModule | null> {
		if (!browser) return null;
		duckdbCacheModulePromise ??= import('$lib/duckdb-cache');
		return duckdbCacheModulePromise;
	}

	async function clearDuckDBCache() {
		const duckdbCache = await getDuckDBCacheModule();
		await duckdbCache?.clearCache();
	}

	let { children }: { children: Snippet } = $props();

	let map: Map | undefined = $state();
	let featureSidebarRef: FeatureSidebar | undefined = $state();
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
	let deckOverlay: DeckTemperatureOverlay | null = null;
	let deckHasData = $state(false);
	let desktopTriplets: Float64Array | null = null;
	let desktopRowCol: Int32Array | null = null;
	let landsatSourceCrs: string | null = null;
	let landsatTransform: AffineTransform | null = null;
	let desktopCellSizeXM = 0;
	let desktopCellSizeYM = 0;
	let desktopHalfPixelX = 0;
	let desktopHalfPixelY = 0;
	let relativeMin = $state(0);
	let relativeMax = $state(0);
	let avgTemp = $state(0);
	let histogramData: Array<{ range: string; count: number }> = $state([]);
	let waterOff = $state(false);
	let dataSource = $state('');
	let pixelSizeDeg = $state<number | null>(null);
	let pixelSizeXDeg = $state<number | null>(null);
	let temperatureLoading = $state(false);
	let rasterPngUrl: string | null = $state(null);
	let loadGen = 0; // incremented each time loadTemperatureData starts; guards stale async results
	const globalMin = 273.15;
	const globalMax = 308.15;

	function resetTileState() {
		deckOverlay?.clear();
		deckHasData = false;
		desktopTriplets = null;
		desktopRowCol = null;
		landsatSourceCrs = null;
		landsatTransform = null;
		rasterPngUrl = null;
		relativeMin = 0;
		relativeMax = 0;
		avgTemp = 0;
		histogramData = [];
		tempFilterMin = null;
		tempFilterMax = null;
		dataSource = '';
		pixelSizeDeg = null;
		pixelSizeXDeg = null;
	}

	let selectedPoint: { longitude: number; latitude: number } | null = $state(null);
	let pointHistoryOpen = $state(false);

	let pointHistoryTolerance = $derived.by(() => {
		const base = Math.max(pixelSizeDeg ?? 0, pixelSizeXDeg ?? 0);
		if (base > 0) return Math.min(Math.max(base * 1.5, 0.0005), 0.01);
		return 0.01;
	});

	function closePointHistory() {
		selectedPoint = null;
		pointHistoryOpen = false;
	}

	// Default map view (MapLibre uses [lng, lat])
	const defaultCenter: [number, number] = [112.5, 2.5];
	const defaultZoom = 6;

	// Saved map position (to restore when closing sidebar)
	let savedMapView: { center: [number, number]; zoom: number } | null = $state(null);

	// URL is the single source of truth
	let urlFeatureId = $derived($page.params.id ?? null);

	// URL search params — schema defines all shareable view state
	const urlSchema = createSearchParamsSchema({
		date:  { type: 'string', default: '' },
		scale: { type: 'string', default: 'relative' },
		unit:  { type: 'string', default: 'C' },
		tmin:  { type: 'string', default: '' },
		tmax:  { type: 'string', default: '' },
		lng:   { type: 'string', default: '' },
		lat:   { type: 'string', default: '' },
		zoom:  { type: 'string', default: '' },
		plng:  { type: 'string', default: '' },
		plat:  { type: 'string', default: '' },
	});
	const params = useSearchParams(urlSchema, {
		pushHistory: false,
		showDefaults: false,
		noScroll: true,
		debounce: 100,
	});

	// Initial filter values derived from URL (passed to sidebar once)
	let initialFilterMin = $derived(params.tmin ? parseFloat(params.tmin) : null);
	let initialFilterMax = $derived(params.tmax ? parseFloat(params.tmax) : null);

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

	// Drawer open state for mobile — opens when a feature is selected, but can be
	// dismissed independently (user can still view the heatmap on the map).
	let drawerOpen = $state(false);
	let previousMobileFeatureId: string | null = null;
	$effect(() => {
		const id = selectedFeature?.id ?? null;
		// Open drawer when a new feature is selected (or first selection)
		if (id && id !== previousMobileFeatureId) {
			drawerOpen = true;
		}
		// Close drawer when feature is deselected
		if (!id) {
			drawerOpen = false;
		}
		previousMobileFeatureId = id;
	});

	function handleDrawerOpenChange(open: boolean) {
		drawerOpen = open;
		// Don't navigate away — keep feature selected so user can explore the heatmap
	}

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

			// Apply URL params for initial state
			const uScale = untrack(() => params.scale);
			const uUnit = untrack(() => params.unit);
			const uLng = untrack(() => params.lng);
			const uLat = untrack(() => params.lat);
			const uZoom = untrack(() => params.zoom);
			const uPlng = untrack(() => params.plng);
			const uPlat = untrack(() => params.plat);

			if (uScale === 'fixed' || uScale === 'gray') selectedColorScale = uScale;
			if (uUnit === 'K') currentUnit = 'Kelvin';
			else if (uUnit === 'F') currentUnit = 'Fahrenheit';

			// Map viewport from URL takes precedence over fitBounds
			if (uLng && uLat && uZoom) {
				currentMap.jumpTo({
					center: [parseFloat(uLng), parseFloat(uLat)],
					zoom: parseFloat(uZoom)
				});
			} else if (bounds) {
				const animate = !isInitialNavigation;
				currentMap.fitBounds(bounds, { padding: 20, animate });
			}

			// Restore selected pixel from URL
			if (uPlng && uPlat) {
				selectedPoint = { longitude: parseFloat(uPlng), latitude: parseFloat(uPlat) };
				pointHistoryOpen = true;
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
			resetTileState();
			closePointHistory();
			void clearDuckDBCache();
		} else if (currentFeatureId && previousFeatureId && currentFeatureId !== previousFeatureId) {
			// Switching features: just zoom to new feature
			if (bounds) {
				currentMap.fitBounds(bounds, { padding: 20 });
			}
			// Reset local UI state
			selectedDate = '';
			selectedColorScale = 'relative';
			resetTileState();
			closePointHistory();
			void clearDuckDBCache();
		}

		previousFeatureId = currentFeatureId;
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


	function handleMapClick(e: MapMouseEvent) {
		if (!map) return;

		// deck.gl's onClick handles temperature picks and sets hoveredTemp.
		// If hoveredTemp is set, the user clicked on temperature data — don't navigate.
		if (hoveredTemp != null) return;

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

		// deck.gl's onHover sets hoveredTemp; if hovering temperature data, show crosshair
		if (hoveredTemp != null) {
			map.getCanvas().style.cursor = 'crosshair';
			return;
		}

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
		// Stamp this invocation so stale completions can be detected and discarded.
		const gen = ++loadGen;

		// Clear previous tile state but keep parquet cache (same feature, different date)
		resetTileState();
		waterOff = false;

		if (!featureId || !date) return;

		temperatureLoading = true;
		try {
			const enc = encodeURIComponent(featureId);

			// Show raster PNG immediately — no awaits needed, browser starts fetching on render
			rasterPngUrl = `/api/feature/${enc}/tif/${encodeURIComponent(date)}/${selectedColorScale}`;

			const meta = await fetchTemperatureMetadata(featureId, date);
			if (gen !== loadGen) return; // newer load started
			if (!meta) return;

			const source = meta.source;
			const duckdbCache = await getDuckDBCacheModule();
			if (gen !== loadGen) return;
			if (!duckdbCache) return;

			const feature = await duckdbCache.fetchDuckDBFeature(featureId, source);
			if (gen !== loadGen) return;
			if (!feature) return;

			const parquetResult = await duckdbCache.getPointsForDate(feature, date, source);
			if (gen !== loadGen) return;
			if (!parquetResult) return;

			const { points: pointsBuffer, stats, rowCol: rowColBuffer } = parquetResult;

			if (pointsBuffer.byteLength < 24 || pointsBuffer.byteLength % 24 !== 0) return;

			pixelSizeDeg = meta.pixelSize;
			pixelSizeXDeg = meta.pixelSizeX ?? pixelSizeDeg;

			landsatSourceCrs = meta.sourceCrs;
			landsatTransform = meta.transform;

			// Stats must be set before deck layer update so relative color scale works
			relativeMin = stats.min;
			relativeMax = stats.max;
			avgTemp = stats.avg;
			histogramData = stats.histogram;

			waterOff = meta.wtoff || false;
			dataSource = meta.source || 'ecostress';

			{
				const f64 = new Float64Array(pointsBuffer);
				desktopTriplets = f64;
				desktopRowCol = rowColBuffer ? new Int32Array(rowColBuffer) : null;
				const bounds = selectedFeature!.bounds as [[number,number],[number,number]];
				const centerLat = (bounds[0][1] + bounds[1][1]) / 2;
				const psx = pixelSizeXDeg ?? pixelSizeDeg ?? 0.0007;
				const psy = pixelSizeDeg ?? 0.0007;
				desktopCellSizeXM = psx * 111_320 * Math.cos(centerLat * Math.PI / 180);
				desktopCellSizeYM = psy * 110_540;
				desktopHalfPixelX = psx / 2;
				desktopHalfPixelY = psy / 2;
				updateDeckLayer();
				deckHasData = true;
				// Remove raster once deck.gl has rendered
				map?.once('idle', () => {
					if (gen === loadGen) rasterPngUrl = null;
				});
			}
			} catch (err) {
			console.error('Error loading temperature data:', err);
		} finally {
			if (gen === loadGen) temperatureLoading = false;
		}
	}

	function switchToDate(date: string) {
		selectedDate = date;
		if (selectedFeature) {
			loadTemperatureData(selectedFeature.id, date);
		}
		params.date = date;
	}

	function handleDateChange(event: CustomEvent<string>) {
		switchToDate(event.detail);
	}

	function handleColorScaleChange(event: CustomEvent<'relative' | 'fixed' | 'gray'>) {
		selectedColorScale = event.detail;
		// Update raster PNG URL when using raster overlay (mobile always, desktop during loading)
		if (rasterPngUrl && selectedFeature && selectedDate) {
			const enc = encodeURIComponent(selectedFeature.id);
			rasterPngUrl = `/api/feature/${enc}/tif/${encodeURIComponent(selectedDate)}/${event.detail}`;
		}
		// Update deck.gl layer colors
		if (desktopTriplets) updateDeckLayer();
		params.scale = event.detail;
	}

	function handleTempFilterChange(event: CustomEvent<{ min: number | null; max: number | null }>) {
		tempFilterMin = event.detail.min;
		tempFilterMax = event.detail.max;
		// Update deck.gl layer filtering
		if (desktopTriplets) updateDeckLayer();
		params.tmin = tempFilterMin != null ? tempFilterMin.toFixed(2) : '';
		params.tmax = tempFilterMax != null ? tempFilterMax.toFixed(2) : '';
	}

	function updateDeckLayer() {
		if (!deckOverlay || !desktopTriplets) return;
		let minTemp = selectedColorScale === 'relative' ? relativeMin : globalMin;
		let maxTemp = selectedColorScale === 'relative' ? relativeMax : globalMax;
		if (minTemp >= maxTemp) {
			minTemp = globalMin;
			maxTemp = globalMax;
		}
		deckOverlay.update({
			triplets: desktopTriplets,
			cellSizeXMeters: desktopCellSizeXM,
			cellSizeYMeters: desktopCellSizeYM,
			halfPixelX: desktopHalfPixelX,
			halfPixelY: desktopHalfPixelY,
			landsatSourceCrs: landsatSourceCrs,
			landsatTransform: landsatTransform,
			rowCol: desktopRowCol,
			colorScale: selectedColorScale,
			minTemp,
			maxTemp,
			filterMin: tempFilterMin,
			filterMax: tempFilterMax,
			onHover: (info) => {
				hoveredTemp = info.temperature;
				tooltipX = info.x;
				tooltipY = info.y;
			},
			onClick: (info) => {
				hoveredTemp = info.temperature;
				selectedPoint = { longitude: info.longitude, latitude: info.latitude };
				pointHistoryOpen = true;
			}
		});
	}

	function handleSidebarClose() {
		// Just change the URL - state will update automatically
		goto('/', { replaceState: false, keepFocus: true, noScroll: true });
		// Focus the map canvas so arrow keys work for panning
		map?.getCanvas().focus();
	}

	function handleLayoutKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && selectedFeature) {
			e.preventDefault();
			handleSidebarClose();
		}
	}

	// Right-click context menu state
	let contextMenuOpen = $state(false);
	let contextMenuX = $state(0);
	let contextMenuY = $state(0);
	let contextMenuLngLat: { lng: number; lat: number } | null = $state(null);
	let mapContainerEl: HTMLDivElement | undefined = $state();

	function handleMapContextMenu(e: MouseEvent) {
		if (!map) return;
		e.preventDefault();
		const rect = map.getCanvas().getBoundingClientRect();
		const point = { x: e.clientX - rect.left, y: e.clientY - rect.top };
		const lngLat = map.unproject(point as any);
		contextMenuLngLat = { lng: lngLat.lng, lat: lngLat.lat };
		// Position menu, clamping to viewport so it doesn't overflow
		const menuW = 180;
		const menuH = 80;
		contextMenuX = Math.min(e.clientX, window.innerWidth - menuW);
		contextMenuY = Math.min(e.clientY, window.innerHeight - menuH);
		contextMenuOpen = true;
	}

	function closeContextMenu() {
		contextMenuOpen = false;
	}

	function handleViewHistoryHere() {
		if (!contextMenuLngLat || !selectedFeature) return;
		selectedPoint = { longitude: contextMenuLngLat.lng, latitude: contextMenuLngLat.lat };
		pointHistoryOpen = true;
		closeContextMenu();
	}

	function handleCopyCoordinates() {
		if (!contextMenuLngLat) return;
		const text = `${contextMenuLngLat.lat.toFixed(6)}, ${contextMenuLngLat.lng.toFixed(6)}`;
		navigator.clipboard.writeText(text);
		toast.success('Coordinates copied', { description: text });
		closeContextMenu();
	}

	// Close context menu on click outside, scroll, or Escape
	function handleWindowClick() {
		if (contextMenuOpen) closeContextMenu();
	}
	function handleWindowKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && contextMenuOpen) {
			e.preventDefault();
			e.stopPropagation();
			closeContextMenu();
		}
	}

	// Attach contextmenu listener to map container (captures events from deck.gl overlay too)
	$effect(() => {
		const el = mapContainerEl;
		if (!el) return;
		el.addEventListener('contextmenu', handleMapContextMenu);
		return () => el.removeEventListener('contextmenu', handleMapContextMenu);
	});

	function handleMapLoad() {
		mapReady = true;
	}

	onMount(async () => {
		// Start downloading the DuckDB WASM bundle immediately so the first
		// query doesn't pay the cold-start cost.
		getDuckDBCacheModule().then((m) => m?.preload());

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
	
	let tooltipSourceLabel = $derived(dataSource === 'landsat' ? ' · Landsat' : dataSource === 'ecostress' ? ' · ECOSTRESS' : '');
	let tooltipTempDisplay = $derived(
		hoveredTemp != null ? convertTemp(hoveredTemp).toFixed(1) + unitSymbol + tooltipSourceLabel : ''
	);

	// Image source coordinates for mobile raster overlay: [topLeft, topRight, bottomRight, bottomLeft]
	let rasterCoordinates = $derived.by((): [[number,number],[number,number],[number,number],[number,number]] | null => {
		if (!selectedFeature?.bounds) return null;
		const [[minLng, minLat], [maxLng, maxLat]] = selectedFeature.bounds as [[number,number],[number,number]];
		return [
			[minLng, maxLat], // top-left
			[maxLng, maxLat], // top-right
			[maxLng, minLat], // bottom-right
			[minLng, minLat], // bottom-left
		];
	});

	let selectedPointGeoJSON = $derived.by(() => {
		const pt = selectedPoint;
		if (!pt) {
			return {
				type: 'FeatureCollection' as const,
				features: []
			};
		}
		return {
			type: 'FeatureCollection' as const,
			features: [
				{
					type: 'Feature' as const,
					properties: {},
					geometry: {
						type: 'Point' as const,
						coordinates: [pt.longitude, pt.latitude] as [number, number]
					}
				}
			]
		};
	});

	// deck.gl overlay lifecycle: create when map is ready, clean up on destroy
	$effect(() => {
		if (!map || !mapReady) return;

		let overlay: DeckTemperatureOverlay;

		// Dynamic import for code-splitting — deck.gl only loads when needed
		import('$lib/deck-temperature-overlay').then(({ DeckTemperatureOverlay: Cls }) => {
			overlay = new Cls();
			overlay.addTo(map!);
			deckOverlay = overlay;
			// If data was loaded before overlay was ready, render it now
			if (desktopTriplets) updateDeckLayer();
		});

		return () => {
			if (overlay) {
				overlay.remove();
			}
			deckOverlay = null;
		};
	});

	// Sync map viewport to URL on move (debounced by useSearchParams)
	$effect(() => {
		if (!map || !mapReady) return;
		const m = map;
		const handler = () => {
			if (!selectedFeature) return;
			const c = m.getCenter();
			params.update({
				lng: c.lng.toFixed(4),
				lat: c.lat.toFixed(4),
				zoom: m.getZoom().toFixed(2),
			});
		};
		m.on('moveend', handler);
		return () => { m.off('moveend', handler); };
	});

	// Sync unit to URL (untrack selectedFeature to avoid loop: params write → $page update → selectedFeature re-derive)
	$effect(() => {
		if (!untrack(() => selectedFeature)) return;
		params.unit = currentUnit === 'Kelvin' ? 'K' : currentUnit === 'Fahrenheit' ? 'F' : 'C';
	});

	// Sync selected pixel to URL
	$effect(() => {
		if (!untrack(() => selectedFeature)) return;
		params.plng = selectedPoint ? selectedPoint.longitude.toFixed(5) : '';
		params.plat = selectedPoint ? selectedPoint.latitude.toFixed(5) : '';
	});
</script>

<svelte:head>
	<title>{selectedFeature ? `${selectedFeature.name} — Satellite Water Temps` : 'Satellite Water Temperature Monitoring'}</title>
</svelte:head>

<svelte:window onkeydown={(e) => { handleWindowKeydown(e); handleLayoutKeydown(e); }} onclick={handleWindowClick} />

<Sidebar.Provider open={sidebarOpen} onOpenChange={(open) => { if (!open) handleSidebarClose(); }}>
	<div class="flex h-screen w-full">
		<!-- Feature Sidebar (desktop only) – only in DOM when a feature is selected -->
		{#if selectedFeature && !isMobile.current}
			<Sidebar.Sidebar side="left" collapsible="offcanvas" class="border-r w-full sm:max-w-md">
				<Sidebar.Header class="flex flex-row items-center justify-between gap-2 px-4 py-3 border-b shrink-0 bg-background">
					<span class="font-semibold text-foreground truncate">
						{selectedFeature.name ?? selectedFeature.id ?? 'Water body'}
					</span>
					<Tooltip.Provider>
						<Tooltip.Root>
							<Tooltip.Trigger>
								{#snippet child({ props })}
									<Button {...props} variant="ghost" size="icon-sm" onclick={handleSidebarClose} class="shrink-0">
										<XIcon class="size-4" />
										<span class="sr-only">Close</span>
									</Button>
								{/snippet}
							</Tooltip.Trigger>
							<Tooltip.Content side="bottom">
								<span class="inline-flex items-center gap-1.5"><Kbd>Esc</Kbd> Close</span>
							</Tooltip.Content>
						</Tooltip.Root>
					</Tooltip.Provider>
				</Sidebar.Header>
				<Sidebar.Content class="flex flex-col min-h-0 bg-background">
					<FeatureSidebar
						bind:this={featureSidebarRef}
						featureId={selectedFeature.id}
						featureName={selectedFeature.name ?? ''}
						initialDate={params.date}
						{initialFilterMin}
						{initialFilterMax}
						bind:selectedDate
						bind:selectedColorScale
						bind:currentUnit
						bind:dataSource
						{relativeMin}
						{relativeMax}
						{avgTemp}
						{histogramData}
						{waterOff}
						{temperatureLoading}
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
			<div class="flex-1 relative w-full" bind:this={mapContainerEl}>
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
				onmouseout={() => { hoveredTemp = null; }}
				onmovestart={() => { hoveredTemp = null; closeContextMenu(); }}
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
					<GeoJSONSource id="selected-point" data={selectedPointGeoJSON}>
						<CircleLayer
							id="selected-point-layer"
							paint={{
								'circle-radius': 5,
								'circle-color': '#ffffff',
								'circle-stroke-color': '#111827',
								'circle-stroke-width': 2
							}}
						/>
					</GeoJSONSource>

				{#if rasterCoordinates}
					<!-- Raster PNG overlay (instant preview; stays underneath vector tiles until they render).
					     Kept always mounted (no {#key}) so MapLibre calls updateImage() on URL changes
					     instead of removeSource/addSource, which avoids "Source already exists" races. -->
					<ImageSource
						id="temperature-raster"
						url={rasterPngUrl ?? 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'}
						coordinates={rasterCoordinates}
					>
						{#if rasterPngUrl}
							<RasterLayer
								id="temperature-raster-layer"
								paint={{ 'raster-opacity': 0.85, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' }}
							/>
						{/if}
					</ImageSource>
				{/if}
				</MapLibre>
				<!-- Floating search bar (top left) -->
				{#if !sidebarOpen}
					<FeatureSearch {geojsonData} />
				{/if}
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

				{#if !isMobile.current && pointHistoryOpen}
					<div class="absolute right-4 bottom-4 z-40">
						<PointHistoryPanel
							{selectedPoint}
							featureId={selectedFeature?.id ?? null}
							{dataSource}
							{selectedDate}
							unit={currentUnit}
							{deckOverlay}
							halfPixelX={desktopHalfPixelX}
							halfPixelY={desktopHalfPixelY}
							pixelTolerance={pointHistoryTolerance}
							{getDuckDBCacheModule}
							onclose={closePointHistory}
							ondatechange={switchToDate}
						/>
					</div>
				{/if}

				<!-- Keyboard navigation hint (desktop only, when feature has data loaded) -->
				{#if !isMobile.current && selectedFeature && deckHasData}
					<div class="absolute bottom-3 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-md bg-background/80 backdrop-blur-sm px-3 py-1.5 shadow-sm border border-border/50">
						<button class="inline-flex items-center gap-1 cursor-pointer hover:text-foreground text-muted-foreground transition-colors" onclick={() => featureSidebarRef?.navigateDate(-1)}>
							<span class="inline-flex items-center gap-0.5"><Kbd>{modKeyLabel}</Kbd><Kbd>←</Kbd></span>
							<span class="text-[11px]">Previous</span>
						</button>
						<span class="text-muted-foreground/40 mx-1">|</span>
						<button class="inline-flex items-center gap-1 cursor-pointer hover:text-foreground text-muted-foreground transition-colors" onclick={() => featureSidebarRef?.navigateDate(1)}>
							<span class="text-[11px]">Next</span>
							<span class="inline-flex items-center gap-0.5"><Kbd>{modKeyLabel}</Kbd><Kbd>→</Kbd></span>
						</button>
					</div>
				{/if}
			</div>

		</main>
	</div>

	<!-- Mobile: bottom bar + drawer -->
	{#if isMobile.current && selectedFeature}
		<!-- Bottom bar (always visible when feature selected, acts as drawer trigger) -->
		{#if !drawerOpen}
			<button
				class="fixed bottom-0 inset-x-0 z-40 flex items-center gap-3 px-4 py-3 bg-background border-t shadow-lg"
				onclick={() => { drawerOpen = true; }}
			>
				<ChevronUpIcon class="size-5 text-muted-foreground shrink-0" />
				<span class="font-semibold text-foreground truncate flex-1 text-left">
					{selectedFeature.name ?? selectedFeature.id ?? 'Water body'}
				</span>
				<Button
					variant="ghost"
					size="icon-sm"
					class="shrink-0"
					onclick={(e: MouseEvent) => { e.stopPropagation(); handleSidebarClose(); }}
				>
					<XIcon class="size-4" />
					<span class="sr-only">Close</span>
				</Button>
			</button>
		{/if}

		<!-- Drawer (slides up with full feature details) -->
		<Drawer.Root open={drawerOpen} onOpenChange={handleDrawerOpenChange}>
			<Drawer.Content class="max-h-[85vh]">
				<Drawer.Header class="flex flex-row items-center justify-between gap-2 px-4 py-3 border-b">
					<Drawer.Title class="font-semibold text-foreground truncate">
						{selectedFeature.name ?? selectedFeature.id ?? 'Water body'}
					</Drawer.Title>
					<Button variant="ghost" size="icon-sm" onclick={() => handleSidebarClose()} class="shrink-0">
						<XIcon class="size-4" />
						<span class="sr-only">Close</span>
					</Button>
				</Drawer.Header>
				<div class="overflow-y-auto flex-1 min-h-0">
					<FeatureSidebar
						bind:this={featureSidebarRef}
						featureId={selectedFeature.id}
						featureName={selectedFeature.name ?? ''}
						initialDate={params.date}
						{initialFilterMin}
						{initialFilterMax}
						bind:selectedDate
						bind:selectedColorScale
						bind:currentUnit
						bind:dataSource
						{relativeMin}
						{relativeMax}
						{avgTemp}
						{histogramData}
						{waterOff}
						{temperatureLoading}
						on:close={handleSidebarClose}
						on:dateChange={handleDateChange}
						on:colorScaleChange={handleColorScaleChange}
						on:tempFilterChange={handleTempFilterChange}
					/>
				</div>
			</Drawer.Content>
		</Drawer.Root>
	{/if}

	{#if isMobile.current}
		<Dialog.Root open={pointHistoryOpen} onOpenChange={(open) => { if (!open) closePointHistory(); }}>
			<Dialog.Content class="max-w-[calc(100%-1.5rem)] p-0" showCloseButton={false}>
				<PointHistoryPanel
					{selectedPoint}
					featureId={selectedFeature?.id ?? null}
					{dataSource}
					{selectedDate}
					unit={currentUnit}
					{deckOverlay}
					halfPixelX={desktopHalfPixelX}
					halfPixelY={desktopHalfPixelY}
					pixelTolerance={pointHistoryTolerance}
					{getDuckDBCacheModule}
					onclose={closePointHistory}
					ondatechange={switchToDate}
				/>
			</Dialog.Content>
		</Dialog.Root>
	{/if}

	<!-- Right-click context menu (custom, to work over deck.gl overlay) -->
	{#if contextMenuOpen && contextMenuLngLat}
		<div
			class="fixed z-50 min-w-36 rounded-lg p-1 shadow-md bg-popover text-popover-foreground ring-1 ring-foreground/10 animate-in fade-in-0 zoom-in-95"
			style="left: {contextMenuX}px; top: {contextMenuY}px;"
			role="menu"
		>
			<div class="px-2 py-1.5 text-xs text-muted-foreground tabular-nums">
				{contextMenuLngLat.lat.toFixed(6)}, {contextMenuLngLat.lng.toFixed(6)}
			</div>
			<div class="bg-border -mx-1 my-1 h-px"></div>
			<button
				role="menuitem"
				class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-hidden select-none hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50"
				disabled={!selectedFeature}
				onclick={handleViewHistoryHere}
			>
				<HistoryIcon class="size-4 shrink-0" />
				<span class="flex-1">View history here</span>
				<Kbd class="text-[10px]">Click</Kbd>
			</button>
			<button
				role="menuitem"
				class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-hidden select-none hover:bg-accent hover:text-accent-foreground"
				onclick={handleCopyCoordinates}
			>
				<CopyIcon class="size-4 shrink-0" />
				Copy coordinates
			</button>
		</div>
	{/if}

	<!-- Hidden slot for child pages (they don't render anything) -->
	<div class="hidden">
		{@render children()}
	</div>
</Sidebar.Provider>
