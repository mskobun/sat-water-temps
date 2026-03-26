import { json } from '@sveltejs/kit';
import { queryObservationMeta } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;

	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const featureId = params.id;
	const date = params.date;

	const result = await queryObservationMeta(db, featureId, date);

	if (!result) {
		return json({ error: 'Temperature data not found' }, { status: 404 });
	}

	return json(result, {
		headers: {
			'cache-control': 'public, max-age=120'
		}
	});
};
