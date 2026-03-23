import geojsonvt from 'geojson-vt';
import { fromGeojsonVt } from 'vt-pbf';
import type { AddProtocolAction } from 'maplibre-gl';

type PointTriplet = [lng: number, lat: number, temperature: number];

interface TileIndex {
	loadFn: AddProtocolAction;
	destroy: () => void;
}

/**
 * Convert flat [lng, lat, temp] triplets to a GeoJSON Point FeatureCollection.
 */
function tripletsToPoints(points: PointTriplet[]): GeoJSON.FeatureCollection {
	return {
		type: 'FeatureCollection',
		features: points.map((p) => ({
			type: 'Feature' as const,
			geometry: { type: 'Point' as const, coordinates: [p[0], p[1]] },
			properties: { temperature: p[2] }
		}))
	};
}

/**
 * Convert a Point FeatureCollection into square Polygons for pixel-fill rendering.
 */
function pointsToSquares(
	fc: GeoJSON.FeatureCollection,
	pixelSizeX: number,
	pixelSizeY: number
): GeoJSON.FeatureCollection {
	const halfX = pixelSizeX / 2;
	const halfY = pixelSizeY / 2;
	return {
		type: 'FeatureCollection',
		features: fc.features.map((f) => {
			const [lng, lat] = (f.geometry as GeoJSON.Point).coordinates;
			return {
				type: 'Feature' as const,
				geometry: {
					type: 'Polygon' as const,
					coordinates: [
						[
							[lng - halfX, lat - halfY],
							[lng + halfX, lat - halfY],
							[lng + halfX, lat + halfY],
							[lng - halfX, lat + halfY],
							[lng - halfX, lat - halfY]
						]
					]
				},
				properties: f.properties
			};
		})
	};
}

/**
 * Create geojson-vt tile indices from raw point data and register
 * a custom protocol handler that serves MVT tiles to MapLibre.
 */
export function createTileIndex(
	points: PointTriplet[],
	pixelSizeX: number | null,
	pixelSizeY: number | null
): TileIndex {
	const vtOpts: geojsonvt.Options = {
		maxZoom: 14,
		tolerance: 0, // points need no simplification
		buffer: 64,
		indexMaxZoom: 5
	};

	const pointsGeoJSON = tripletsToPoints(points);
	let pointsIndex: ReturnType<typeof geojsonvt> | null = geojsonvt(pointsGeoJSON, vtOpts);

	let squaresIndex: ReturnType<typeof geojsonvt> | null = null;
	if (pixelSizeY != null) {
		const psx = pixelSizeX ?? pixelSizeY;
		const squaresGeoJSON = pointsToSquares(pointsGeoJSON, psx, pixelSizeY);
		squaresIndex = geojsonvt(squaresGeoJSON, { ...vtOpts, tolerance: 0 });
	}

	const loadFn: AddProtocolAction = (params, _abortController) => {
		// URL format: temp://tiles/{z}/{x}/{y}
		const re = /(\d+)\/(\d+)\/(\d+)/;
		const match = params.url.match(re);
		if (!match) {
			return Promise.reject(new Error(`Invalid tile URL: ${params.url}`));
		}

		const z = +match[1];
		const x = +match[2];
		const y = +match[3];

		const layers: Record<string, { features: any[] }> = {};

		const ptTile = pointsIndex?.getTile(z, x, y);
		if (ptTile) {
			layers.points = ptTile;
		} else {
			// vt-pbf needs at least an empty features array
			layers.points = { features: [] };
		}

		if (squaresIndex) {
			const sqTile = squaresIndex.getTile(z, x, y);
			if (sqTile) {
				layers.squares = sqTile;
			} else {
				layers.squares = { features: [] };
			}
		}

		const pbf = fromGeojsonVt(layers as any, { version: 2, extent: 4096 });
		return Promise.resolve({ data: pbf.buffer });
	};

	function destroy() {
		pointsIndex = null;
		squaresIndex = null;
	}

	return { loadFn, destroy };
}
