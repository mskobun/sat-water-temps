import proj4 from 'proj4';

/** Rasterio Affine: x = a*col + b*row + c, y = d*col + e*row + f */
export type AffineTransform = {
	a: number;
	b: number;
	c: number;
	d: number;
	e: number;
	f: number;
};

function forwardProjected(col: number, row: number, t: AffineTransform): [number, number] {
	return [t.a * col + t.b * row + t.c, t.d * col + t.e * row + t.f];
}

/**
 * Four corners of pixel [row, col] in WGS84 (lon, lat), CCW from upper-left.
 * Uses pixel index corners (col, row) … (col+1, row+1) in image space.
 */
export function pixelQuadWgs84(
	row: number,
	col: number,
	sourceCrs: string,
	transform: AffineTransform
): [number, number][] {
	const projector = proj4(sourceCrs, 'EPSG:4326');
	const corners: [number, number][] = [
		[col, row],
		[col + 1, row],
		[col + 1, row + 1],
		[col, row + 1]
	];
	return corners.map(([ci, ri]) => {
		const [x, y] = forwardProjected(ci, ri, transform);
		const [lng, lat] = projector.forward([x, y]) as [number, number];
		return [lng, lat];
	});
}

/** One `proj4` instance for all pixels — use for bulk work (main thread or worker). */
export function computeLandsatQuadsFlat(
	sourceCrs: string,
	transform: AffineTransform,
	rowCol: Int32Array,
	count: number
): Float64Array {
	const projector = proj4(sourceCrs, 'EPSG:4326');
	const out = new Float64Array(count * 8);
	for (let i = 0; i < count; i++) {
		const r = rowCol[i * 2]!;
		const c = rowCol[i * 2 + 1]!;
		const corners: [number, number][] = [
			[c, r],
			[c + 1, r],
			[c + 1, r + 1],
			[c, r + 1]
		];
		let o = i * 8;
		for (let j = 0; j < 4; j++) {
			const [ci, ri] = corners[j]!;
			const [x, y] = forwardProjected(ci, ri, transform);
			const [lng, lat] = projector.forward([x, y]) as [number, number];
			out[o++] = lng;
			out[o++] = lat;
		}
	}
	return out;
}

/** Unpack flat buffer from {@link computeLandsatQuadsFlat} (cheap; runs on main thread). */
export function flatQuadsToPolygons(flat: Float64Array, count: number): [number, number][][] {
	const polys: [number, number][][] = new Array(count);
	for (let i = 0; i < count; i++) {
		const o = i * 8;
		polys[i] = [
			[flat[o], flat[o + 1]],
			[flat[o + 2], flat[o + 3]],
			[flat[o + 4], flat[o + 5]],
			[flat[o + 6], flat[o + 7]],
		];
	}
	return polys;
}

function isFiniteAffine(t: AffineTransform): boolean {
	return [t.a, t.b, t.c, t.d, t.e, t.f].every((x) => Number.isFinite(x));
}

export function hasLandsatQuadInputs(
	sourceCrs: string | null,
	transform: AffineTransform | null,
	rowCol: Int32Array | null
): transform is AffineTransform {
	return (
		sourceCrs != null &&
		sourceCrs.length > 0 &&
		transform != null &&
		isFiniteAffine(transform) &&
		rowCol != null &&
		rowCol.length >= 2
	);
}
