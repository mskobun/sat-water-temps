import * as duckdb from '@duckdb/duckdb-wasm';

// Use runtime CDN assets so large WASM binaries are not emitted into
// SvelteKit/Pages build artifacts (Cloudflare Pages limit: 25 MiB/file).
const CDN_BUNDLES: duckdb.DuckDBBundles = duckdb.getJsDelivrBundles();

type SourceType = 'ecostress' | 'landsat';

interface RegisteredParquetFile {
	name: string;
	url: string;
}

export interface CachedDuckDBFeature {
	featureId: string;
	source: SourceType;
	files: RegisteredParquetFile[];
}

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
	/** Landsat raster row (present when source is landsat) */
	row?: number;
	/** Landsat raster col (present when source is landsat) */
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

function quoteSqlLiteral(value: string): string {
	return `'${value.replaceAll("'", "''")}'`;
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
				allowFullHTTPReads: false,
				// Must be explicit — omitting this defaults to true in the WASM runtime,
				// which skips both the HEAD probe and the full-read fallback, causing
				// "Failed to open file" with zero network requests made.
				forceFullHTTPReads: false
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
}

async function registerRemoteParquet(
	db: duckdb.AsyncDuckDB,
	name: string,
	url: string
) {
	// DuckDB WASM passes the URL to XMLHttpRequest.open() which requires an
	// absolute URL. Resolve relative paths against the current origin.
	const absoluteUrl = new URL(url, globalThis.location.origin).href;
	// directIO: false — let the buffer manager coalesce nearby reads into fewer,
	// larger range requests. Range-request enforcement is handled at the DB level
	// via forceFullHTTPReads: false + allowFullHTTPReads: false in db.open().
	await db.registerFileURL(name, absoluteUrl, duckdb.DuckDBDataProtocol.HTTP, false);
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

		const db = await getDb(source);
		const filteredEntries = entries.filter(({ path }) =>
			source === 'landsat' ? path.startsWith('LANDSAT/') : path.startsWith('ECO/')
		);
		if (filteredEntries.length === 0) return null;

		const files = filteredEntries.map(({ path }, index) => ({
			name: featureFileName(featureId, index),
			url: `/api/feature/${enc}/parquet?path=${encodeURIComponent(path)}`
		}));

		await Promise.all(
			files.map((file) => registerRemoteParquet(db, file.name, file.url))
		);

		cachedBySource[source] = {
			featureId,
			source,
			files
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
 * Landsat: also returns rowCol (interleaved row, col per point) when present in Parquet.
 */
export async function getPointsForDate(
	feature: CachedDuckDBFeature,
	date: string,
	source: SourceType
): Promise<{
	points: ArrayBuffer;
	stats: TemperatureStats;
	rowCol?: ArrayBufferLike;
} | null> {
	const chunks: Float64Array[] = [];
	const rowColChunks: Int32Array[] = [];
	let totalRows = 0;
	let landsatHasRowCol: boolean | null = source === 'landsat' ? null : false;

	for (const file of feature.files) {
		let table;
		if (source === 'landsat' && landsatHasRowCol !== false) {
			try {
				table = await withConnection(source, (connection) =>
					connection.query(`
				SELECT longitude, latitude, temperature, "row", "col"
				FROM ${quoteSqlLiteral(file.name)}
				WHERE date = ${quoteSqlLiteral(date)}
			`)
				);
				landsatHasRowCol = true;
			} catch {
				table = await withConnection(source, (connection) =>
					connection.query(`
				SELECT longitude, latitude, temperature
				FROM ${quoteSqlLiteral(file.name)}
				WHERE date = ${quoteSqlLiteral(date)}
			`)
				);
				landsatHasRowCol = false;
			}
		} else {
			table = await withConnection(source, (connection) =>
				connection.query(`
				SELECT longitude, latitude, temperature
				FROM ${quoteSqlLiteral(file.name)}
				WHERE date = ${quoteSqlLiteral(date)}
			`)
			);
		}

		if (table.numRows === 0) continue;
		const longitude = table.getChild('longitude');
		const latitude = table.getChild('latitude');
		const temperature = table.getChild('temperature');
		if (!longitude || !latitude || !temperature) continue;

		const chunk = new Float64Array(table.numRows * 3);
		let offset = 0;
		for (let i = 0; i < table.numRows; i++) {
			chunk[offset++] = Number(longitude.get(i));
			chunk[offset++] = Number(latitude.get(i));
			chunk[offset++] = Number(temperature.get(i));
		}
		totalRows += table.numRows;
		chunks.push(chunk);

		if (landsatHasRowCol === true) {
			const rowChild = table.getChild('row');
			const colChild = table.getChild('col');
			if (!rowChild || !colChild) {
				landsatHasRowCol = false;
			} else {
				const rc = new Int32Array(table.numRows * 2);
				let ro = 0;
				for (let i = 0; i < table.numRows; i++) {
					rc[ro++] = Number(rowChild.get(i));
					rc[ro++] = Number(colChild.get(i));
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
		landsatHasRowCol === true &&
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
	} else if (source === 'landsat') {
		// Sentinel so deck overlay falls back to lon/lat rectangles
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

	const isLandsat = source === 'landsat';

	for (const file of feature.files) {
		const rowColSelect = isLandsat ? ', "row", "col"' : '';
		const query = `
			WITH candidates AS (
				SELECT
					date,
					longitude,
					latitude,
					temperature${isLandsat ? ', "row", "col"' : ''},
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
					temperature${rowColSelect},
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
				temperature${rowColSelect},
				SQRT(distance_squared) AS distance
			FROM ranked
			WHERE row_number = 1
				AND distance_squared <= ${formatFiniteNumber(toleranceSquared)}
			ORDER BY date
		`;

		const table = await withConnection(source, (connection) => connection.query(query));

		if (table.numRows === 0) continue;

		const dateVector = table.getChild('date');
		const longitudeVector = table.getChild('longitude');
		const latitudeVector = table.getChild('latitude');
		const temperatureVector = table.getChild('temperature');
		const distanceVector = table.getChild('distance');
		if (!dateVector || !longitudeVector || !latitudeVector || !temperatureVector || !distanceVector) {
			continue;
		}

		const rowVector = isLandsat ? table.getChild('row') : null;
		const colVector = isLandsat ? table.getChild('col') : null;

		for (let i = 0; i < table.numRows; i++) {
			const entry: PointHistoryEntry = {
				date: String(dateVector.get(i)),
				longitude: Number(longitudeVector.get(i)),
				latitude: Number(latitudeVector.get(i)),
				temperature: Number(temperatureVector.get(i)),
				distance: Number(distanceVector.get(i)),
				source
			};
			if (rowVector && colVector) {
				entry.row = Number(rowVector.get(i));
				entry.col = Number(colVector.get(i));
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

export async function clearCache() {
	for (const source of ['ecostress', 'landsat'] as const) {
		const cached = cachedBySource[source];
		if (!cached) continue;
		await dropRegisteredFiles(source, cached.files);
		cachedBySource[source] = null;
	}
}
