import { json } from '@sveltejs/kit';
import { getFeatureStatsHistory } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const featureId = params.id;

	try {
		const entries = await getFeatureStatsHistory(db, featureId);
		return json(
			{
				entries,
				last_updated: new Date().toISOString()
			},
			{
				headers: {
					'cache-control': 'public, max-age=120'
				}
			}
		);
	} catch (err) {
		console.error('D1 query error:', err);
		return json({ error: 'Database error' }, { status: 500 });
	}
};
