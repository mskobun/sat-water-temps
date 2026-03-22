/**
 * Date utilities for ISO datetime format (YYYY-MM-DDTHH:MM:SS).
 *
 * All dates in the database are normalized to this format:
 *   ECOSTRESS: "2024-12-27T04:19:23"
 *   Landsat:   "2024-12-27T00:00:00"
 */

/**
 * Convert a date string to a JS Date object.
 * Primary format: "YYYY-MM-DDTHH:MM:SS"
 * Legacy fallbacks kept for transition period.
 */
export function parseDate(date: string): Date {
	if (date.length === 19 && date[10] === 'T') {
		return new Date(date);
	}
	// Legacy: bare ISO date
	if (date.length === 10 && date[4] === '-') {
		return new Date(date + 'T00:00:00');
	}
	// Legacy: ECOSTRESS DOY format
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
 * Calendar day key (YYYY-MM-DD) — just the date portion.
 */
export function dateStringToCalendarKey(date: string): string {
	return date.substring(0, 10);
}

/**
 * Full date/time display: "dd/mm/yyyy hh:mm:ss" or "dd/mm/yyyy" if midnight.
 */
export function formatDateTime(date: string): string {
	const d = parseDate(date);
	const day = String(d.getDate()).padStart(2, '0');
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const year = d.getFullYear();
	const time = date.length >= 19 ? date.substring(11) : null;
	if (!time || time === '00:00:00') return `${day}/${month}/${year}`;
	return `${day}/${month}/${year} ${time}`;
}

/**
 * Short display: "27 Dec 2024".
 */
export function formatShortDate(date: string): string {
	const d = parseDate(date);
	return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Compare two date strings chronologically.
 * With normalized ISO datetime format, string comparison works directly.
 */
export function compareDates(a: string, b: string): number {
	return a.localeCompare(b);
}

/**
 * Source label for display.
 */
export function sourceLabel(source: string): string {
	if (source === 'landsat') return 'Landsat';
	return 'ECOSTRESS';
}
