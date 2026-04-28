export interface FilterStats {
	total_pixels: number;
	histogram: Record<string, number>;
}

export interface ParsedFilterStats {
	total: number;
	valid: number;
	filtered: number;
	filtered_by_qc: number;
	filtered_by_cloud: number;
	filtered_by_water: number;
	filtered_by_opera_water: number;
	filtered_by_nodata: number;
}

// Bit 0=QC, Bit 1=Cloud, Bit 2=Water (native), Bit 3=NoData,
// Bit 4=Range outlier, Bit 5=Spatial outlier, Bit 6=Water (OPERA)
const BIT_NAMES = ['QC', 'Cloud', 'Water (native)', 'NoData', 'Range outlier', 'Spatial outlier', 'Water (OPERA)'];

function bucketLabel(bucket: number): string {
	const names: string[] = [];
	for (let b = 0; b < BIT_NAMES.length; b++) {
		if (bucket & (1 << b)) names.push(BIT_NAMES[b]);
	}
	return names.join(' + ');
}

export interface CombinationRow {
	label: string;
	count: number;
	pct: number;
}

export function hasHistogram(stats: FilterStats | null | undefined): boolean {
	if (!stats || typeof stats !== 'object') return false;
	const anyStats = stats as any;
	const hist = anyStats.histogram;
	return !!hist && typeof hist === 'object';
}

function getHistogram(stats: FilterStats | null | undefined): Record<string, number> {
	if (!stats || typeof stats !== 'object') return {};
	const hist = (stats as Partial<FilterStats>).histogram;
	if (!hist || typeof hist !== 'object') return {};
	return hist as Record<string, number>;
}

function getTotalPixels(stats: FilterStats | null | undefined, hist: Record<string, number>): number {
	if (stats && typeof stats.total_pixels === 'number' && Number.isFinite(stats.total_pixels)) {
		return stats.total_pixels;
	}
	// Fallback for malformed/legacy rows: derive total from histogram buckets.
	return Object.values(hist).reduce((sum, value) => sum + (Number(value) || 0), 0);
}

/** Return non-zero histogram buckets as labeled rows, sorted by count descending. */
export function getFilterCombinations(stats: FilterStats): CombinationRow[] {
	const hist = getHistogram(stats);
	const total = getTotalPixels(stats, hist);
	if (total === 0) return [];

	const rows: CombinationRow[] = [];
	// 7 bits → max bucket value 127
	for (let i = 1; i < 128; i++) {
		const count = hist[i.toString()] || 0;
		if (count > 0) {
			rows.push({
				label: bucketLabel(i),
				count,
				pct: (count / total) * 100,
			});
		}
	}
	rows.sort((a, b) => b.count - a.count);
	return rows;
}

/**
 * Parse a bit-flag histogram into named filter statistics.
 * Bit 0 = QC, Bit 1 = Cloud, Bit 2 = Water (native), Bit 3 = NoData
 * Bit 4 = Range outlier, Bit 5 = Spatial outlier, Bit 6 = Water (OPERA DSWx)
 *
 * QC/cloud/water counts exclude nodata pixels.
 * NoData count includes all buckets with bit 3 set regardless of other flags.
 */
export function parseFilterStats(stats: FilterStats): ParsedFilterStats {
	const hist = getHistogram(stats);
	const total = getTotalPixels(stats, hist);
	const valid = hist['0'] || 0;

	let filtered_by_qc = 0;
	let filtered_by_cloud = 0;
	let filtered_by_water = 0;
	let filtered_by_opera_water = 0;
	let filtered_by_nodata = 0;

	for (let i = 1; i < 128; i++) {
		const count = hist[i.toString()] || 0;
		if (!count) continue;
		if (i & 8) {
			// Bit 3 set: nodata — count towards nodata, skip other categories
			filtered_by_nodata += count;
			continue;
		}
		if (i & 1) filtered_by_qc += count;
		if (i & 2) filtered_by_cloud += count;
		if (i & 4) filtered_by_water += count;
		if (i & 64) filtered_by_opera_water += count;
	}

	return {
		total,
		valid,
		filtered: total - valid,
		filtered_by_qc,
		filtered_by_cloud,
		filtered_by_water,
		filtered_by_opera_water,
		filtered_by_nodata,
	};
}
