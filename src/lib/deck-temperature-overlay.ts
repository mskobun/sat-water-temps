import { MapboxOverlay } from '@deck.gl/mapbox';
import { SolidPolygonLayer, PathLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import type { Map } from 'maplibre-gl';
import type { PickingInfo } from '@deck.gl/core';

import type { AffineTransform } from '$lib/landsat-pixel-quads';
import {
	computeLandsatQuadsFlat,
	flatQuadsToPolygons,
	hasLandsatQuadInputs
} from '$lib/landsat-pixel-quads';

export interface UpdateOptions {
	triplets: Float64Array;
	cellSizeXMeters: number;
	cellSizeYMeters: number;
	/** Half pixel width in degrees (triplets are pixel centers; X/Y may differ for non-square pixels) */
	halfPixelX: number;
	/** Half pixel height in degrees */
	halfPixelY: number;
	/** Landsat: native CRS + affine + per-pixel row/col → exact WGS84 quads */
	landsatSourceCrs?: string | null;
	landsatTransform?: AffineTransform | null;
	/** Interleaved row, col per pixel (length 2 * count); use with landsat fields */
	rowCol?: Int32Array | null;
	colorScale: 'relative' | 'fixed' | 'gray';
	minTemp: number;
	maxTemp: number;
	filterMin: number | null;
	filterMax: number | null;
	onHover: (info: { temperature: number | null; x: number; y: number }) => void;
	onClick: (info: { longitude: number; latitude: number; temperature: number }) => void;
}

/**
 * Piecewise-linear interpolation matching matplotlib's segment data format.
 * Each stop is [position, value]. Clamps outside [0,1].
 */
function piecewise(t: number, stops: [number, number][]): number {
	if (t <= stops[0][0]) return stops[0][1];
	for (let i = 1; i < stops.length; i++) {
		if (t <= stops[i][0]) {
			const [x0, y0] = stops[i - 1];
			const [x1, y1] = stops[i];
			return y0 + (y1 - y0) * ((t - x0) / (x1 - x0));
		}
	}
	return stops[stops.length - 1][1];
}

/**
 * Matplotlib "jet" colormap — exact channel definitions from matplotlib/_cm.py.
 *   red:   (0,0) (0.35,0) (0.66,1) (0.89,1) (1,0.5)
 *   green: (0,0) (0.125,0) (0.375,1) (0.64,1) (0.91,0) (1,0)
 *   blue:  (0,0.5) (0.11,1) (0.34,1) (0.65,0) (1,0)
 */
const JET_R: [number, number][] = [[0, 0], [0.35, 0], [0.66, 1], [0.89, 1], [1, 0.5]];
const JET_G: [number, number][] = [[0, 0], [0.125, 0], [0.375, 1], [0.64, 1], [0.91, 0], [1, 0]];
const JET_B: [number, number][] = [[0, 0.5], [0.11, 1], [0.34, 1], [0.65, 0], [1, 0]];

function tempToRGBA(
	temp: number,
	scale: 'relative' | 'fixed' | 'gray',
	min: number,
	max: number
): [number, number, number, number] {
	if (scale === 'gray') {
		const t = max > min ? (temp - min) / (max - min) : 0.5;
		const v = Math.round(40 + Math.max(0, Math.min(1, t)) * 215);
		return [v, v, v, 255];
	}

	const t = max > min ? Math.max(0, Math.min(1, (temp - min) / (max - min))) : 0.5;

	const r = Math.round(piecewise(t, JET_R) * 255);
	const g = Math.round(piecewise(t, JET_G) * 255);
	const b = Math.round(piecewise(t, JET_B) * 255);
	return [r, g, b, 255];
}

function createTemperatureLayer(
	opts: UpdateOptions,
	mode: 'rect' | 'landsat-precomputed',
	landsatPolygons: [number, number][][] | null
): SolidPolygonLayer {
	const {
		triplets,
		halfPixelX,
		halfPixelY,
		colorScale,
		minTemp,
		maxTemp,
		filterMin,
		filterMax,
		onHover,
		onClick
	} = opts;

	const count = (triplets.length / 3) | 0;
	const hasFilter = filterMin != null && filterMax != null;
	const fMin = filterMin ?? 0;
	const fMax = filterMax ?? 0;

	const data =
		mode === 'landsat-precomputed' && landsatPolygons ? landsatPolygons : { length: count };

	return new SolidPolygonLayer({
		id: 'temperature-cells',
		beforeId: 'selected-point-layer',
		data,
		getPolygon:
			mode === 'landsat-precomputed' && landsatPolygons
				? (d: [number, number][]) => d
				: (_: unknown, { index }: { index: number }) => {
						const o = index * 3;
						const lng = triplets[o];
						const lat = triplets[o + 1];
						const x0 = lng - halfPixelX;
						const x1 = lng + halfPixelX;
						const y0 = lat - halfPixelY;
						const y1 = lat + halfPixelY;
						return [
							[x0, y0],
							[x1, y0],
							[x1, y1],
							[x0, y1]
						];
					},
		extruded: false,
		filled: true,
		getFillColor: (_: unknown, { index }: { index: number }) => {
			const temp = triplets[index * 3 + 2];
			if (hasFilter && (temp < fMin || temp > fMax)) {
				return [0, 0, 0, 0];
			}
			return tempToRGBA(temp, colorScale, minTemp, maxTemp);
		},
		material: false,
		pickable: true,
		onHover: (info: PickingInfo) => {
			if (info.index >= 0) {
				const temp = triplets[info.index * 3 + 2];
				if (hasFilter && (temp < fMin || temp > fMax)) {
					onHover({ temperature: null, x: info.x, y: info.y });
				} else {
					onHover({ temperature: temp, x: info.x, y: info.y });
				}
			} else {
				onHover({ temperature: null, x: info.x, y: info.y });
			}
		},
		onClick: (info: PickingInfo) => {
			if (info.index >= 0) {
				const o = info.index * 3;
				const temp = triplets[o + 2];
				if (hasFilter && (temp < fMin || temp > fMax)) return;
				onClick({
					longitude: triplets[o],
					latitude: triplets[o + 1],
					temperature: temp
				});
			}
		},
		updateTriggers: {
			getFillColor: [colorScale, minTemp, maxTemp, filterMin, filterMax],
			getPolygon:
				mode === 'landsat-precomputed' && landsatPolygons
					? [landsatPolygons]
					: [triplets, halfPixelX, halfPixelY]
		}
	});
}

export class DeckTemperatureOverlay {
	private overlay: MapboxOverlay;
	private map: Map | null = null;
	private mainLayer: SolidPolygonLayer | null = null;
	private highlightFill: SolidPolygonLayer | null = null;
	private highlightStroke: PathLayer | null = null;

	constructor() {
		this.overlay = new MapboxOverlay({
			interleaved: true,
			layers: []
		});
	}

	addTo(map: Map): void {
		this.map = map;
		map.addControl(this.overlay as unknown as maplibregl.IControl);
	}

	remove(): void {
		if (this.map) {
			this.map.removeControl(this.overlay as unknown as maplibregl.IControl);
			this.map = null;
		}
	}

	update(opts: UpdateOptions): void {
		const {
			triplets,
			landsatSourceCrs,
			landsatTransform,
			rowCol
		} = opts;

		const count = (triplets.length / 3) | 0;
		if (count === 0) {
			this.clear();
			return;
		}

		const useLandsatQuads =
			hasLandsatQuadInputs(landsatSourceCrs ?? null, landsatTransform ?? null, rowCol ?? null) &&
			rowCol!.length === count * 2 &&
			rowCol![0] !== -1;

		if (!useLandsatQuads) {
			this.mainLayer = createTemperatureLayer(opts, 'rect', null);
		} else {
			const crs = landsatSourceCrs!;
			const tf = landsatTransform!;

			try {
				const flat = computeLandsatQuadsFlat(crs, tf, rowCol!, count);
				const polygons = flatQuadsToPolygons(flat, count);
				this.mainLayer = createTemperatureLayer(opts, 'landsat-precomputed', polygons);
			} catch (err) {
				console.error('[deck] Landsat quad compute failed:', err);
				this.mainLayer = createTemperatureLayer(opts, 'rect', null);
			}
		}

		this.syncLayers();
	}

	setHighlight(polygon: [number, number][] | null): void {
		if (!polygon) {
			this.highlightFill = null;
			this.highlightStroke = null;
		} else {
			// Close the ring for PathLayer
			const ring = [...polygon, polygon[0]];
			this.highlightFill = new SolidPolygonLayer({
				id: 'highlight-pixel-fill',
				beforeId: 'selected-point-layer',
				data: [polygon],
				getPolygon: (d: [number, number][]) => d,
				getFillColor: [255, 255, 255, 50],
				extruded: false,
				material: false,
				pickable: false
			});
			this.highlightStroke = new PathLayer({
				id: 'highlight-pixel-stroke',
				beforeId: 'selected-point-layer',
				data: [ring],
				getPath: (d: [number, number][]) => d,
				getColor: [255, 255, 0, 240],
				widthMinPixels: 3,
				getDashArray: [6, 4],
				dashJustified: true,
				extensions: [new PathStyleExtension({ dash: true })],
				pickable: false
			});
		}
		this.syncLayers();
	}

	private syncLayers(): void {
		const layers = [this.mainLayer, this.highlightFill, this.highlightStroke].filter(Boolean);
		this.overlay.setProps({ layers });
	}

	clear(): void {
		this.mainLayer = null;
		this.highlightFill = null;
		this.highlightStroke = null;
		this.overlay.setProps({ layers: [] });
	}
}
