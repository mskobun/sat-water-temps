import { json } from '@sveltejs/kit';
import { getFeatureDates } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	// Join the array from rest parameter back into a string
	const featureId = params.id;
	const dates = await getFeatureDates(db, featureId);

	return json(dates, {
		headers: {
			'cache-control': 'public, max-age=120'
		}
	});
};

