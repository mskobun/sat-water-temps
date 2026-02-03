import { json } from '@sveltejs/kit';
import { getEcostressRequests } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const limit = parseInt(url.searchParams.get('limit') || '50');
	const status = url.searchParams.get('status') || undefined;

	const requests = await getEcostressRequests(db, limit, status);

	return json({ requests }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
