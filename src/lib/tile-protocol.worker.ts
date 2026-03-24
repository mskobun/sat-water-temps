import geojsonvt from 'geojson-vt';
import { fromGeojsonVt } from 'vt-pbf';

let pointsIndex: ReturnType<typeof geojsonvt> | null = null;
let squaresIndex: ReturnType<typeof geojsonvt> | null = null;

function tripletsToPointsPacked(f32: Float32Array): GeoJSON.FeatureCollection {
	const n = (f32.length / 3) | 0;
	const features = new Array<GeoJSON.Feature>(n);
	for (let i = 0, j = 0; i < n; i++, j += 3) {
		features[i] = {
			type: 'Feature' as const,
			geometry: { type: 'Point' as const, coordinates: [f32[j], f32[j + 1]] },
			properties: { temperature: f32[j + 2] }
		};
	}
	return {
		type: 'FeatureCollection',
		features
	};
}

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

const vtOpts: geojsonvt.Options = {
	maxZoom: 14,
	tolerance: 0,
	buffer: 64,
	indexMaxZoom: 5
};

self.onmessage = (e: MessageEvent) => {
	const msg = e.data;

	if (msg.type === 'init') {
		const pointsBuffer: ArrayBuffer = msg.pointsBuffer;
		const pixelSizeX: number | null = msg.pixelSizeX;
		const pixelSizeY: number | null = msg.pixelSizeY;

		const f32 = new Float32Array(pointsBuffer);
		pointsIndex = null;
		squaresIndex = null;
		if (f32.length === 0 || f32.length % 3 !== 0) {
			const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
			pointsIndex = geojsonvt(empty, vtOpts);
		} else {
			const pointsGeoJSON = tripletsToPointsPacked(f32);
			pointsIndex = geojsonvt(pointsGeoJSON, vtOpts);

			if (pixelSizeY != null) {
				const psx = pixelSizeX ?? pixelSizeY;
				const squaresGeoJSON = pointsToSquares(pointsGeoJSON, psx, pixelSizeY);
				squaresIndex = geojsonvt(squaresGeoJSON, vtOpts);
			}
		}

		self.postMessage({ type: 'ready' });
	} else if (msg.type === 'getTile') {
		const { id, z, x, y } = msg;

		const layers: Record<string, { features: unknown[] }> = {};

		const ptTile = pointsIndex?.getTile(z, x, y);
		layers.points = ptTile ?? { features: [] };

		if (squaresIndex) {
			const sqTile = squaresIndex.getTile(z, x, y);
			layers.squares = sqTile ?? { features: [] };
		}

		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const pbf = fromGeojsonVt(layers as any, { version: 2, extent: 4096 });
		const buffer = pbf.buffer;
		self.postMessage({ type: 'tile', id, buffer }, { transfer: [buffer] });
	}
};
