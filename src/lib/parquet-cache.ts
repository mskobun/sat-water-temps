/**
 * Client-side Parquet cache using range requests via hyparquet's asyncBufferFromUrl.
 * Fetches only metadata footer on feature open (~512kb), then per-date row group
 * column chunks on date change (~50-200kb).
 */
import { parquetMetadataAsync, parquetRead, asyncBufferFromUrl, cachedAsyncBuffer } from 'hyparquet';
import { compressors } from 'hyparquet-compressors';
import type { AsyncBuffer, FileMetaData } from 'hyparquet';

interface ParquetFile {
	asyncBuffer: AsyncBuffer;
	metadata: FileMetaData;
	/** Map from date string → row group index */
	dateIndex: Map<string, number>;
}

export interface CachedParquet {
	featureId: string;
	files: ParquetFile[];
}

export interface TemperatureStats {
	min: number;
	max: number;
	avg: number;
	histogram: Array<{ range: string; count: number }>;
}

let cached: CachedParquet | null = null;

function buildDateIndex(metadata: FileMetaData): Map<string, number> {
	const dateIndex = new Map<string, number>();

	for (let i = 0; i < metadata.row_groups.length; i++) {
		const rg = metadata.row_groups[i];
		const dateCol = rg.columns.find(
			(c: any) => c.meta_data?.path_in_schema?.includes('date')
		);
		const minVal = dateCol?.meta_data?.statistics?.min_value;
		if (minVal != null) {
			dateIndex.set(typeof minVal === 'string' ? minVal : String(minVal), i);
		}
	}

	return dateIndex;
}

/**
 * Fetch Parquet metadata for a feature using range requests.
 * Only reads the footer (~512kb per file), not the whole file.
 */
export async function fetchParquet(featureId: string): Promise<CachedParquet | null> {
	if (cached && cached.featureId === featureId) return cached;

	const enc = encodeURIComponent(featureId);

	// Get list of parquet paths with sizes
	const listRes = await fetch(`/api/feature/${enc}/parquet`);
	if (!listRes.ok) return null;

	const entries: Array<{ path: string; size: number }> = await listRes.json();
	if (entries.length === 0) return null;

	// Create async buffers and fetch metadata in parallel (range requests only)
	const files: ParquetFile[] = [];
	const results = await Promise.all(
		entries.map(async ({ path, size }) => {
			const url = `/api/feature/${enc}/parquet?path=${encodeURIComponent(path)}`;
			const asyncBuffer = cachedAsyncBuffer(
				await asyncBufferFromUrl({ url, byteLength: size })
			);
			const metadata = await parquetMetadataAsync(asyncBuffer);
			const dateIndex = buildDateIndex(metadata);
			return { asyncBuffer, metadata, dateIndex };
		})
	);

	for (const result of results) {
		files.push(result);
	}

	if (files.length === 0) return null;

	cached = { featureId, files };
	return cached;
}

/** Find which cached file contains a given date. */
function findFileForDate(parquet: CachedParquet, date: string): { file: ParquetFile; rgIndex: number } | null {
	for (const file of parquet.files) {
		const rgIndex = file.dateIndex.get(date);
		if (rgIndex !== undefined) return { file, rgIndex };
	}
	return null;
}

function computeHistogram(temps: Float32Array, numBins = 6): Array<{ range: string; count: number }> {
	if (!temps.length) return [];

	let min = Infinity;
	let max = -Infinity;
	for (let i = 0; i < temps.length; i++) {
		const t = temps[i];
		if (t < min) min = t;
		if (t > max) max = t;
	}
	const binWidth = (max - min) / numBins;
	if (binWidth === 0) {
		return [{ range: min.toFixed(1), count: temps.length }];
	}

	const bins = new Array(numBins).fill(0);
	for (let i = 0; i < temps.length; i++) {
		const idx = Math.min(Math.floor((temps[i] - min) / binWidth), numBins - 1);
		bins[idx]++;
	}

	return bins.map((count, i) => ({
		range: (min + i * binWidth).toFixed(1),
		count
	}));
}

function computeStats(points: Float32Array): TemperatureStats {
	const count = points.length / 3;
	let min = Infinity;
	let max = -Infinity;
	let sum = 0;

	// Extract temperatures into a separate array for histogram
	const temps = new Float32Array(count);
	for (let i = 0; i < count; i++) {
		const t = points[i * 3 + 2];
		temps[i] = t;
		if (t < min) min = t;
		if (t > max) max = t;
		sum += t;
	}

	return {
		min,
		max,
		avg: count > 0 ? sum / count : 0,
		histogram: computeHistogram(temps)
	};
}

/**
 * Extract points for a specific date using range requests.
 * Returns packed Float32 triplets (lng, lat, temperature) and computed stats.
 */
export async function getPointsForDate(
	parquet: CachedParquet,
	date: string
): Promise<{ points: ArrayBuffer; stats: TemperatureStats } | null> {
	const match = findFileForDate(parquet, date);
	if (!match) return null;

	const { file, rgIndex } = match;
	let rowStart = 0;
	for (let i = 0; i < rgIndex; i++) {
		rowStart += Number(file.metadata.row_groups[i].num_rows);
	}
	const rowEnd = rowStart + Number(file.metadata.row_groups[rgIndex].num_rows);

	let rows: any[] = [];
	await parquetRead({
		file: file.asyncBuffer,
		metadata: file.metadata,
		compressors,
		rowStart,
		rowEnd,
		columns: ['longitude', 'latitude', 'temperature'],
		onComplete: (data: any[]) => { rows = data; }
	});

	if (rows.length === 0) return null;

	const out = new Float32Array(rows.length * 3);
	let o = 0;
	for (const row of rows) {
		out[o++] = Number(row[0]); // longitude
		out[o++] = Number(row[1]); // latitude
		out[o++] = Number(row[2]); // temperature
	}

	const stats = computeStats(out);

	return { points: out.buffer, stats };
}

/** Clear the cached Parquet (call when switching features). */
export function clearCache() {
	cached = null;
}

/** Get all dates available across cached Parquet files. */
export function getAvailableDates(parquet: CachedParquet): string[] {
	const dates = new Set<string>();
	for (const file of parquet.files) {
		for (const date of file.dateIndex.keys()) {
			dates.add(date);
		}
	}
	return Array.from(dates).sort();
}
