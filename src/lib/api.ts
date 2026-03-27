import type { AffineTransform } from '$lib/landsat-pixel-quads';

export interface TemperatureMetadata {
	date: string;
	wtoff: boolean;
	source: 'ecostress' | 'landsat';
	pixelSize: number | null;
	pixelSizeX: number | null;
	sourceCrs: string | null;
	transform: AffineTransform | null;
}

const metadataCache: Record<string, TemperatureMetadata> = {};

export async function fetchTemperatureMetadata(
	featureId: string,
	date: string
): Promise<TemperatureMetadata | null> {
	const key = `${featureId}:${date}`;
	if (metadataCache[key]) return metadataCache[key];

	const enc = encodeURIComponent(featureId);
	const res = await fetch(`/api/feature/${enc}/temperature/${encodeURIComponent(date)}`);
	if (!res.ok) return null;

	const raw = await res.json();
	if (raw.error) return null;

	const hasTf =
		raw.transform_a != null &&
		raw.transform_b != null &&
		raw.transform_c != null &&
		raw.transform_d != null &&
		raw.transform_e != null &&
		raw.transform_f != null;

	const meta: TemperatureMetadata = {
		date: raw.date,
		wtoff: raw.wtoff || false,
		source: raw.source === 'landsat' ? 'landsat' : 'ecostress',
		pixelSize: raw.pixel_size ?? null,
		pixelSizeX: raw.pixel_size_x ?? null,
		sourceCrs: raw.source_crs ?? null,
		transform: hasTf
			? {
					a: Number(raw.transform_a),
					b: Number(raw.transform_b),
					c: Number(raw.transform_c),
					d: Number(raw.transform_d),
					e: Number(raw.transform_e),
					f: Number(raw.transform_f)
				}
			: null
	};

	metadataCache[key] = meta;
	return meta;
}
