/**
 * Centralized date utilities for handling both ECOSTRESS (DOY) and Landsat (ISO) date formats.
 *
 * ECOSTRESS dates: 13-digit DOY — "YYYYDDDhhmmss" e.g. "2024362041923"
 * Landsat dates:   ISO 8601     — "YYYY-MM-DD"    e.g. "2024-12-27"
 */

export function isIsoDate(date: string): boolean {
	return date.length === 10 && date[4] === '-';
}

/**
 * Convert any date string to a JS Date object.
 * For DOY dates, parses year + day-of-year + optional time.
 * For ISO dates, parses YYYY-MM-DD.
 */
export function parseDate(date: string): Date {
	if (isIsoDate(date)) {
		return new Date(date + 'T00:00:00');
	}
	const year = parseInt(date.substring(0, 4), 10);
	const doy = parseInt(date.substring(4, 7), 10);
	const hours = date.length >= 9 ? parseInt(date.substring(7, 9), 10) : 0;
	const minutes = date.length >= 11 ? parseInt(date.substring(9, 11), 10) : 0;
	const seconds = date.length >= 13 ? parseInt(date.substring(11, 13), 10) : 0;
	const d = new Date(year, 0);
	d.setDate(doy);
	d.setHours(hours, minutes, seconds);
	return d;
}

/**
 * Convert any date to a sortable ISO string (YYYY-MM-DD or YYYY-MM-DDThh:mm:ss).
 * Used for chronological comparison across ECOSTRESS and Landsat dates.
 */
export function toSortableDate(date: string): string {
	if (isIsoDate(date)) return date;
	const d = parseDate(date);
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	const hh = String(d.getHours()).padStart(2, '0');
	const mm = String(d.getMinutes()).padStart(2, '0');
	const ss = String(d.getSeconds()).padStart(2, '0');
	return `${y}-${m}-${day}T${hh}:${mm}:${ss}`;
}

/**
 * Full date/time display: "dd/mm/yyyy hh:mm:ss" for DOY, "dd/mm/yyyy" for ISO.
 */
export function formatDateTime(date: string): string {
	if (isIsoDate(date)) {
		const [year, month, day] = date.split('-');
		return `${day}/${month}/${year}`;
	}
	const year = date.substring(0, 4);
	const doy = parseInt(date.substring(4, 7), 10);
	const hours = date.substring(7, 9);
	const minutes = date.substring(9, 11);
	const seconds = date.substring(11, 13);
	const dateObj = new Date(parseInt(year), 0);
	dateObj.setDate(doy);
	const day = String(dateObj.getDate()).padStart(2, '0');
	const month = String(dateObj.getMonth() + 1).padStart(2, '0');
	return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}

/**
 * Short display: "27 Dec 2024".
 */
export function formatShortDate(date: string): string {
	const d = parseDate(date);
	return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Compare two date strings chronologically (works across DOY and ISO formats).
 * Returns negative if a < b, positive if a > b, 0 if equal.
 */
export function compareDates(a: string, b: string): number {
	return toSortableDate(a).localeCompare(toSortableDate(b));
}

/**
 * Source label for display — always full names for consistency.
 */
export function sourceLabel(source: string): string {
	if (source === 'landsat') return 'Landsat';
	return 'ECOSTRESS';
}
