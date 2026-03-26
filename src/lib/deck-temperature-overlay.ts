import { MapboxOverlay } from '@deck.gl/mapbox';
import { GridCellLayer } from '@deck.gl/layers';
import type { Map } from 'maplibre-gl';
import type { PickingInfo } from '@deck.gl/core';

export interface UpdateOptions {
	triplets: Float32Array;
	cellSizeXMeters: number;
	cellSizeYMeters: number;
	/** Offset to shift from center → bottom-left corner (degrees) */
	halfPixelX: number;
	halfPixelY: number;
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

export class DeckTemperatureOverlay {
	private overlay: MapboxOverlay;
	private map: Map | null = null;

	constructor() {
		this.overlay = new MapboxOverlay({
			layers: []
		});
	}

	addTo(map: Map): void {
		this.map = map;
		// MapboxOverlay implements IControl
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
			cellSizeXMeters,
			cellSizeYMeters,
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
		if (count === 0) {
			this.clear();
			return;
		}

		const hasFilter = filterMin != null && filterMax != null;
		const fMin = filterMin ?? 0;
		const fMax = filterMax ?? 0;

		// Use max dimension for square cell size
		const cellSize = Math.max(cellSizeXMeters, cellSizeYMeters);

		const layer = new GridCellLayer({
			id: 'temperature-cells',
			data: { length: count },
			// GridCellLayer expects bottom-left corner; triplets store center
			getPosition: (_: unknown, { index }: { index: number }) => {
				const o = index * 3;
				return [triplets[o] - halfPixelX, triplets[o + 1] - halfPixelY];
			},
			getFillColor: (_: unknown, { index }: { index: number }) => {
				const temp = triplets[index * 3 + 2];
				if (hasFilter && (temp < fMin || temp > fMax)) {
					return [0, 0, 0, 0];
				}
				return tempToRGBA(temp, colorScale, minTemp, maxTemp);
			},
			cellSize,
			extruded: false,
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
				getPosition: [triplets]
			}
		});

		this.overlay.setProps({ layers: [layer] });
	}

	clear(): void {
		this.overlay.setProps({ layers: [] });
	}
}
