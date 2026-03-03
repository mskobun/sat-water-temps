import { json } from '@sveltejs/kit';
import { getFeatures } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const features = await getFeatures(db);

	return json({ features }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
