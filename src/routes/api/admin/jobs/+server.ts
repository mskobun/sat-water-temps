import { json } from '@sveltejs/kit';
import { getProcessingJobs, countJobsByStatus, countJobsByFilter } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const limit = parseInt(url.searchParams.get('limit') || '50');
	const page = parseInt(url.searchParams.get('page') || '1');
	const status = url.searchParams.get('status') || undefined;
	const offset = (page - 1) * limit;

	const [jobs, statusCounts, total] = await Promise.all([
		getProcessingJobs(db, limit, status, offset),
		countJobsByStatus(db),
		countJobsByFilter(db, status),
	]);

	return json({ jobs, total, status_counts: statusCounts, page, limit }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
