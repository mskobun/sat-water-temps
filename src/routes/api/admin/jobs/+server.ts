import { json } from '@sveltejs/kit';
import { getProcessingJobs } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const limit = parseInt(url.searchParams.get('limit') || '100');
	const status = url.searchParams.get('status') || undefined;

	const jobs = await getProcessingJobs(db, limit, status);

	return json({ jobs }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};

