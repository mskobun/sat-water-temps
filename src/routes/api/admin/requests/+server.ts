import { json } from '@sveltejs/kit';
import { countDataRequestsByFilter, countDataRequestsByStatus, getDataRequests } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const limit = parseInt(url.searchParams.get('limit') || '50');
	const page = parseInt(url.searchParams.get('page') || '1');
	const status = url.searchParams.get('status') || undefined;
	const source = (url.searchParams.get('source') || 'ecostress') as 'ecostress' | 'landsat';
	const offset = (page - 1) * limit;

	const [requests, statusCounts, total] = await Promise.all([
		getDataRequests(db, source, limit, status, offset),
		countDataRequestsByStatus(db, source),
		countDataRequestsByFilter(db, source, status),
	]);

	return json({ requests, total, status_counts: statusCounts, page, limit }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
