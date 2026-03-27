export function resolveSourceDateFromChartDetails(
	details: unknown,
	resolveFallbackDate?: (xDate: Date) => string | null | undefined
): string | null {
	if (!details || typeof details !== 'object') return null;

	const detailObj = details as Record<string, unknown>;
	const data = detailObj.data as Record<string, unknown> | undefined;
	if (!data) return null;

	if (typeof data.sourceDate === 'string') return data.sourceDate;

	const x = data.x;
	const xDate =
		x instanceof Date
			? x
			: typeof x === 'string' || typeof x === 'number'
				? new Date(x)
				: null;
	if (!xDate || Number.isNaN(xDate.getTime())) return null;

	return resolveFallbackDate?.(xDate) ?? null;
}
