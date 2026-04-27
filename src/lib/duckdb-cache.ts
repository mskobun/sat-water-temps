import * as duckdb from '@duckdb/duckdb-wasm';
import type { Table } from 'apache-arrow';
import { writable } from 'svelte/store';

// Use runtime CDN assets so large WASM binaries are not emitted into
// SvelteKit/Pages build artifacts (Cloudflare Pages limit: 25 MiB/file).
const CDN_BUNDLES: duckdb.DuckDBBundles = duckdb.getJsDelivrBundles();

type SourceType = 'ecostress' | 'landsat';

interface RegisteredParquetFile {
	name: string;
	url: string;
	/** Original R2 key (matches temperature_metadata.parquet_path). */
	path: string;
}

export interface CachedDuckDBFeature {
	featureId: string;
	source: SourceType;
	files: RegisteredParquetFile[];
	totalBytes: number;
}

/** Live download progress for the current parquet fetch. Null when idle. */
export const parquetLoadProgress = writable<{ loaded: number; total: number } | null>(null);

export interface TemperatureStats {
	min: number;
	max: number;
	avg: number;
	histogram: Array<{ range: string; count: number }>;
}

export interface PointHistoryEntry {
	date: string;
	temperature: number;
	longitude: number;
	latitude: number;
	distance: number;
	source: SourceType;
	/** Raster row (present when parquet has non-null row/col, i.e. projected CRS sources) */
	row?: number;
	/** Raster col (present when parquet has non-null row/col, i.e. projected CRS sources) */
	col?: number;
}

const dbPromises: Record<SourceType, Promise<duckdb.AsyncDuckDB> | null> = {
	ecostress: null,
	landsat: null
};
const cachedBySource: Record<SourceType, CachedDuckDBFeature | null> = {
	ecostress: null,
	landsat: null
};
// Serializes concurrent fetchDuckDBFeature calls per source so that drop+register
// is never interleaved, which would leave orphaned file registrations in the WASM heap.
const fetchLockBySource: Record<SourceType, Promise<unknown>> = {
	ecostress: Promise.resolve(),
	landsat: Promise.resolve()
};
// Tracks which logical file names are currently registered with the WASM FS,
// so ensureFilesRegistered() can skip already-registered parquets.
const registeredNames: Record<SourceType, Set<string>> = {
	ecostress: new Set(),
	landsat: new Set()
};
// Serializes registerFileURL calls per source to guard against two concurrent
// getPointsForDate() calls racing to register the same file.
const registerLockBySource: Record<SourceType, Promise<unknown>> = {
	ecostress: Promise.resolve(),
	landsat: Promise.resolve()
};

function quoteSqlLiteral(value: string): string {
	return `'${value.replaceAll("'", "''")}'`;
}

/** Match Parquet `date` (TIMESTAMP UTC) to the UI/D1 ISO string. */
function sqlDateEqualsUiDate(date: string): string {
	return `date = CAST(${quoteSqlLiteral(date)} AS TIMESTAMP)`;
}

/** Format DuckDB/Arrow timestamp values as D1-style `YYYY-MM-DDTHH:MM:SS` for API URLs. */
function arrowDateCellToApiIso(value: unknown): string {
	if (value == null) return '';
	const pad = (n: number) => String(n).padStart(2, '0');
	if (value instanceof Date) {
		return `${value.getUTCFullYear()}-${pad(value.getUTCMonth() + 1)}-${pad(value.getUTCDate())}T${pad(value.getUTCHours())}:${pad(value.getUTCMinutes())}:${pad(value.getUTCSeconds())}`;
	}
	if (typeof value === 'number' && Number.isFinite(value)) {
		// Arrow timestamps are often microseconds since epoch; JS Date wants ms.
		const ms = value > 1e14 ? value / 1000 : value;
		const d = new Date(ms);
		return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
	}
	if (typeof value === 'bigint') {
		const n = Number(value);
		const ms = n > 1e14 ? n / 1000 : n;
		const d = new Date(ms);
		return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
	}
	if (typeof value === 'string') {
		if (value.length === 10 && value[4] === '-') return `${value}T00:00:00`;
		return value;
	}
	return String(value);
}

function formatFiniteNumber(value: number): string {
	if (!Number.isFinite(value)) {
		throw new Error(`Expected a finite number, received ${value}`);
	}
	return String(value);
}

function featureFileName(featureId: string, index: number): string {
	const safeFeatureId = featureId
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '_')
		.replace(/^_+|_+$/g, '');
	return `${safeFeatureId || 'feature'}_${index}.parquet`;
}

function computeHistogram(
	temps: Float64Array,
	numBins = 6
): Array<{ range: string; count: number }> {
	if (!temps.length) return [];

	let min = Infinity;
	let max = -Infinity;
	for (let i = 0; i < temps.length; i++) {
		const temp = temps[i];
		if (temp < min) min = temp;
		if (temp > max) max = temp;
	}

	const binWidth = (max - min) / numBins;
	if (binWidth === 0) {
		return [{ range: min.toFixed(1), count: temps.length }];
	}

	const bins = new Array(numBins).fill(0);
	for (let i = 0; i < temps.length; i++) {
		const index = Math.min(Math.floor((temps[i] - min) / binWidth), numBins - 1);
		bins[index]++;
	}

	return bins.map((count, index) => ({
		range: (min + index * binWidth).toFixed(1),
		count
	}));
}

function computeStats(points: Float64Array): TemperatureStats {
	const count = points.length / 3;
	let min = Infinity;
	let max = -Infinity;
	let sum = 0;
	const temps = new Float64Array(count);

	for (let i = 0; i < count; i++) {
		const temp = points[i * 3 + 2];
		temps[i] = temp;
		if (temp < min) min = temp;
		if (temp > max) max = temp;
		sum += temp;
	}

	return {
		min,
		max,
		avg: count > 0 ? sum / count : 0,
		histogram: computeHistogram(temps)
	};
}

async function getDb(source: SourceType): Promise<duckdb.AsyncDuckDB> {
	const existing = dbPromises[source];
	if (existing) return existing;

	dbPromises[source] = (async () => {
		const bundle = await duckdb.selectBundle(CDN_BUNDLES);
		// Cross-origin workers are blocked by browsers; proxy through a blob URL
		const workerUrl = bundle.mainWorker!;
		const blob = new Blob([`importScripts(${JSON.stringify(workerUrl)});`], {
			type: 'text/javascript'
		});
		const worker = new Worker(URL.createObjectURL(blob));
		const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
		await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
		await db.open({
			filesystem: {
				reliableHeadRequests: true,
				allowFullHTTPReads: true,
				forceFullHTTPReads: true
			}
		});
		return db;
	})();

	return dbPromises[source]!;
}

async function withConnection<T>(
	source: SourceType,
	callback: (connection: duckdb.AsyncDuckDBConnection) => Promise<T>
): Promise<T> {
	const db = await getDb(source);
	const connection = await db.connect();
	try {
		return await callback(connection);
	} finally {
		await connection.close();
	}
}

async function dropRegisteredFiles(source: SourceType, files: RegisteredParquetFile[]) {
	if (!files.length) return;
	const db = await getDb(source);
	await db.dropFiles(files.map((file) => file.name));
	const registered = registeredNames[source];
	for (const file of files) registered.delete(file.name);
}

/**
 * Register any files not already known to the WASM FS. Serialized per source so
 * concurrent callers (e.g. rapid date switching) don't issue duplicate registrations.
 */
async function ensureFilesRegistered(
	source: SourceType,
	files: RegisteredParquetFile[]
): Promise<void> {
	const result = registerLockBySource[source].then(async () => {
		const registered = registeredNames[source];
		const missing = files.filter((file) => !registered.has(file.name));
		if (missing.length === 0) return;
		const db = await getDb(source);
		// Register sequentially so per-file byte progress accumulates cleanly.
		let loadedSoFar = 0;
		for (const file of missing) {
			const fileBytes = await registerRemoteParquet(db, file.name, file.url, (fileLoaded) => {
				parquetLoadProgress.update(
					(prev) => (prev ? { ...prev, loaded: loadedSoFar + fileLoaded } : null)
				);
			});
			loadedSoFar += fileBytes;
		}
		for (const file of missing) registered.add(file.name);
	});
	registerLockBySource[source] = result.then(
		() => undefined,
		() => undefined
	);
	await result;
}

/** Fetch a remote Parquet file as a buffer and register it with DuckDB's WASM FS.
 * Uses streaming fetch so `onProgress` receives cumulative bytes loaded for this file.
 * Returns the total number of bytes fetched.
 */
async function registerRemoteParquet(
	db: duckdb.AsyncDuckDB,
	name: string,
	url: string,
	onProgress: (loaded: number) => void
): Promise<number> {
	const absoluteUrl = new URL(url, globalThis.location.origin).href;
	const response = await fetch(absoluteUrl);
	if (!response.ok) throw new Error(`Failed to fetch parquet ${url}: ${response.status}`);
	const reader = response.body!.getReader();
	const chunks: Uint8Array[] = [];
	let loaded = 0;
	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		chunks.push(value);
		loaded += value.byteLength;
		onProgress(loaded);
	}
	const buffer = new Uint8Array(loaded);
	let offset = 0;
	for (const chunk of chunks) {
		buffer.set(chunk, offset);
		offset += chunk.byteLength;
	}
	await db.registerFileBuffer(name, buffer);
	return loaded;
}

/**
 * Register remote Parquet files for a feature and keep them cached for repeated queries.
 *
 * Calls are serialized per source via fetchLockBySource so that concurrent invocations
 * (e.g. rapid feature switching) never interleave drop+register, which would leave
 * orphaned file registrations in the WASM heap.
 */
export async function fetchDuckDBFeature(
	featureId: string,
	source: SourceType
): Promise<CachedDuckDBFeature | null> {
	// Chain onto the previous call for this source so only one runs at a time.
	const result = fetchLockBySource[source].then(async () => {
		const cached = cachedBySource[source];
		if (cached?.featureId === featureId) return cached;

		const enc = encodeURIComponent(featureId);
		const listResponse = await fetch(`/api/feature/${enc}/parquet`);
		if (!listResponse.ok) return null;

		const entries: Array<{ path: string; size: number }> = await listResponse.json();
		if (entries.length === 0) return null;

		if (cachedBySource[source]) {
			await dropRegisteredFiles(source, cachedBySource[source]!.files);
			cachedBySource[source] = null;
		}

		const filteredEntries = entries.filter(({ path }) =>
			source === 'landsat' ? path.startsWith('LANDSAT/') : path.startsWith('ECO/')
		);
		if (filteredEntries.length === 0) return null;

		const totalBytes = filteredEntries.reduce((sum, e) => sum + e.size, 0);
		parquetLoadProgress.set({ loaded: 0, total: totalBytes });

		const files = filteredEntries.map(({ path }, index) => ({
			name: featureFileName(featureId, index),
			url: `/api/feature/${enc}/parquet?path=${encodeURIComponent(path)}`,
			path
		}));

		cachedBySource[source] = {
			featureId,
			source,
			files,
			totalBytes
		};
		return cachedBySource[source];
	});

	// Keep the lock chain alive regardless of success/failure.
	fetchLockBySource[source] = result.then(
		() => undefined,
		() => undefined
	);

	return result;
}

/**
 * Extract points for a specific date. Returns packed Float64 triplets
 * (lng, lat, temperature) and summary stats for the selected date.
 * Also returns rowCol (interleaved row, col per point) when present in Parquet.
 */
export async function getPointsForDate(
	feature: CachedDuckDBFeature,
	date: string,
	source: SourceType,
	parquetPath: string
): Promise<{
	points: ArrayBuffer;
	stats: TemperatureStats;
	rowCol?: ArrayBufferLike;
} | null> {
	const target = feature.files.find((f) => f.path === parquetPath);
	if (!target) return null;
	await ensureFilesRegistered(source, [target]);

	const chunks: Float64Array[] = [];
	const rowColChunks: Int32Array[] = [];
	let totalRows = 0;
	let hasRowCol: boolean | null = null;

	for (const file of [target]) {
		let table: Table;
		if (hasRowCol !== false) {
			try {
				table = await withConnection(source, (connection) =>
					connection.query(`
				SELECT longitude, latitude, temperature, "row", "col"
				FROM ${quoteSqlLiteral(file.name)}
				WHERE ${sqlDateEqualsUiDate(date)}
			`)
				);
				hasRowCol = true;
			} catch {
				table = await withConnection(source, (connection) =>
					connection.query(`
				SELECT longitude, latitude, temperature
				FROM ${quoteSqlLiteral(file.name)}
				WHERE ${sqlDateEqualsUiDate(date)}
			`)
				);
				hasRowCol = false;
			}
		} else {
			table = await withConnection(source, (connection) =>
				connection.query(`
				SELECT longitude, latitude, temperature
				FROM ${quoteSqlLiteral(file.name)}
				WHERE ${sqlDateEqualsUiDate(date)}
			`)
			);
		}

		const numRows = table.numRows;
		if (numRows === 0) continue;
		const longitude = table.getChild('longitude');
		const latitude = table.getChild('latitude');
		const temperature = table.getChild('temperature');
		if (!longitude || !latitude || !temperature) continue;

		// Arrow Vector.toArray() on a primitive numeric column returns a concatenated
		// TypedArray. Avoids per-row .get(i) virtual dispatch (was ~18 s on main for large features).
		const lngArr = longitude.toArray() as Float64Array;
		const latArr = latitude.toArray() as Float64Array;
		const tempArr = temperature.toArray() as Float64Array;

		const chunk = new Float64Array(numRows * 3);
		for (let i = 0; i < numRows; i++) {
			const o = i * 3;
			chunk[o] = lngArr[i];
			chunk[o + 1] = latArr[i];
			chunk[o + 2] = tempArr[i];
		}
		totalRows += numRows;
		chunks.push(chunk);

		if (hasRowCol === true) {
			const rowChild = table.getChild('row');
			const colChild = table.getChild('col');
			if (!rowChild || !colChild) {
				hasRowCol = false;
			} else if (rowChild.nullCount > 0 || colChild.nullCount > 0) {
				hasRowCol = false;
			} else {
				const rowArr = rowChild.toArray() as ArrayLike<number | bigint>;
				const colArr = colChild.toArray() as ArrayLike<number | bigint>;
				const rc = new Int32Array(numRows * 2);
				for (let i = 0; i < numRows; i++) {
					rc[i * 2] = Number(rowArr[i]);
					rc[i * 2 + 1] = Number(colArr[i]);
				}
				rowColChunks.push(rc);
			}
		}
	}

	if (totalRows === 0) return null;
	const out = new Float64Array(totalRows * 3);
	let cursor = 0;
	for (const chunk of chunks) {
		out.set(chunk, cursor);
		cursor += chunk.length;
	}

	let rowColOut: Int32Array | undefined;
	if (
		hasRowCol === true &&
		rowColChunks.length === chunks.length &&
		rowColChunks.length > 0
	) {
		const merged = new Int32Array(totalRows * 2);
		let rcCursor = 0;
		for (const rc of rowColChunks) {
			merged.set(rc, rcCursor);
			rcCursor += rc.length;
		}
		rowColOut = merged;
	} else {
		rowColOut = new Int32Array(totalRows * 2).fill(-1);
	}

	return {
		points: out.buffer,
		stats: computeStats(out),
		...(rowColOut ? { rowCol: rowColOut.buffer.slice(0) } : {})
	};
}

/**
 * For each date, pick the nearest pixel to the clicked point within the given tolerance.
 * Distances are returned in degrees so the UI can convert or explain them.
 */
export async function getPointHistory(
	feature: CachedDuckDBFeature,
	longitude: number,
	latitude: number,
	tolerance: number,
	source: SourceType
): Promise<PointHistoryEntry[]> {
	const safeTolerance = Math.max(tolerance, 0);
	const minLongitude = longitude - safeTolerance;
	const maxLongitude = longitude + safeTolerance;
	const minLatitude = latitude - safeTolerance;
	const maxLatitude = latitude + safeTolerance;
	const toleranceSquared = safeTolerance * safeTolerance;
	const history: PointHistoryEntry[] = [];

	await ensureFilesRegistered(source, feature.files);

	for (const file of feature.files) {
		const query = `
			WITH candidates AS (
				SELECT
					date,
					longitude,
					latitude,
					temperature, "row", "col",
					POWER(longitude - ${formatFiniteNumber(longitude)}, 2) +
						POWER(latitude - ${formatFiniteNumber(latitude)}, 2) AS distance_squared
				FROM ${quoteSqlLiteral(file.name)}
				WHERE longitude BETWEEN ${formatFiniteNumber(minLongitude)} AND ${formatFiniteNumber(maxLongitude)}
					AND latitude BETWEEN ${formatFiniteNumber(minLatitude)} AND ${formatFiniteNumber(maxLatitude)}
			),
			ranked AS (
				SELECT
					date,
					longitude,
					latitude,
					temperature, "row", "col",
					distance_squared,
					ROW_NUMBER() OVER (
						PARTITION BY date
						ORDER BY distance_squared ASC
					) AS row_number
				FROM candidates
			)
			SELECT
				date,
				longitude,
				latitude,
				temperature, "row", "col",
				SQRT(distance_squared) AS distance
			FROM ranked
			WHERE row_number = 1
				AND distance_squared <= ${formatFiniteNumber(toleranceSquared)}
			ORDER BY date
		`;

		const table = await withConnection(source, (connection) => connection.query(query));

		const numRows = table.numRows;
		if (numRows === 0) continue;

		const dateVector = table.getChild('date');
		const longitudeVector = table.getChild('longitude');
		const latitudeVector = table.getChild('latitude');
		const temperatureVector = table.getChild('temperature');
		const distanceVector = table.getChild('distance');
		if (!dateVector || !longitudeVector || !latitudeVector || !temperatureVector || !distanceVector) {
			continue;
		}

		const rowVector = table.getChild('row');
		const colVector = table.getChild('col');

		// Materialize primitive columns as typed arrays in one shot.
		const lngArr = longitudeVector.toArray() as Float64Array;
		const latArr = latitudeVector.toArray() as Float64Array;
		const tempArr = temperatureVector.toArray() as Float64Array;
		const distArr = distanceVector.toArray() as Float64Array;
		const rowArr =
			rowVector && rowVector.nullCount === 0
				? (rowVector.toArray() as ArrayLike<number | bigint>)
				: null;
		const colArr =
			colVector && colVector.nullCount === 0
				? (colVector.toArray() as ArrayLike<number | bigint>)
				: null;

		for (let i = 0; i < numRows; i++) {
			const entry: PointHistoryEntry = {
				date: arrowDateCellToApiIso(dateVector.get(i)),
				longitude: lngArr[i],
				latitude: latArr[i],
				temperature: tempArr[i],
				distance: distArr[i],
				source
			};
			if (rowArr && colArr) {
				entry.row = Number(rowArr[i]);
				entry.col = Number(colArr[i]);
			}
			history.push(entry);
		}
	}

	// Deduplicate by date in case multiple parquet files exist for one source.
	const bestByDate = new Map<string, PointHistoryEntry>();
	for (const row of history) {
		const current = bestByDate.get(row.date);
		if (!current || row.distance < current.distance) {
			bestByDate.set(row.date, row);
		}
	}
	return Array.from(bestByDate.values()).sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * Prefetch the DuckDB WASM binary into the browser cache so that the first
 * real `getDb()` call doesn't pay the network cost. Does NOT spin up a
 * worker or instantiate a database.
 */
export async function preload(): Promise<void> {
	const bundle = await duckdb.selectBundle(CDN_BUNDLES);
	const urls = [bundle.mainModule, bundle.mainWorker, bundle.pthreadWorker].filter(Boolean) as string[];
	await Promise.all(urls.map((url) => fetch(url, { priority: 'low' } as RequestInit)));
}

export async function clearCache() {
	for (const source of ['ecostress', 'landsat'] as const) {
		const cached = cachedBySource[source];
		if (!cached) continue;
		await dropRegisteredFiles(source, cached.files);
		cachedBySource[source] = null;
	}
}
