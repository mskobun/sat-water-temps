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
	filtered_by_nodata: number;
}

const BIT_NAMES = ['QC', 'Cloud', 'Water', 'NoData'];

function bucketLabel(bucket: number): string {
	const names: string[] = [];
	for (let b = 0; b < 4; b++) {
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
	for (let i = 1; i < 16; i++) {
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
 * Bit 0 = QC, Bit 1 = Cloud, Bit 2 = Water, Bit 3 = NoData
 *
 * QC/cloud/water counts exclude nodata pixels (only buckets 0-7).
 * NoData count includes all buckets 8-15 regardless of other flags.
 */
export function parseFilterStats(stats: FilterStats): ParsedFilterStats {
	const hist = getHistogram(stats);
	const total = getTotalPixels(stats, hist);
	const valid = hist['0'] || 0;

	// QC/cloud/water counts exclude nodata pixels (only i < 8)
	let filtered_by_qc = 0;
	let filtered_by_cloud = 0;
	let filtered_by_water = 0;
	let filtered_by_nodata = 0;

	for (let i = 0; i < 8; i++) {
		const count = hist[i.toString()] || 0;
		if (i & 1) filtered_by_qc += count;
		if (i & 2) filtered_by_cloud += count;
		if (i & 4) filtered_by_water += count;
	}
	for (let i = 8; i < 16; i++) {
		filtered_by_nodata += hist[i.toString()] || 0;
	}

	return {
		total,
		valid,
		filtered: total - valid,
		filtered_by_qc,
		filtered_by_cloud,
		filtered_by_water,
		filtered_by_nodata,
	};
}
