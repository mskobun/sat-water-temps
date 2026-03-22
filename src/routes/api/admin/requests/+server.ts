import { json } from '@sveltejs/kit';
import { getDataRequests } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const limit = parseInt(url.searchParams.get('limit') || '50');
	const status = url.searchParams.get('status') || undefined;
	const source = (url.searchParams.get('source') || 'ecostress') as 'ecostress' | 'landsat';

	const requests = await getDataRequests(db, source, limit, status);

	return json({ requests }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
