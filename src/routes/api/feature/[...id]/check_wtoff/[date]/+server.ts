import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// Check if water is off for a specific date
export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	// Join the array from rest parameter back into a string
	const featureId = params.id;
	
	try {
		const result = await db.prepare(
			"SELECT wtoff FROM temperature_metadata WHERE feature_id = ? AND date = ?"
		).bind(featureId, params.date).first();
		
		if (!result) {
			return json({ wtoff: true });
		}
		
		return json({ wtoff: Boolean(result.wtoff) });
	} catch (err) {
		console.error('D1 query error:', err);
		return json({ wtoff: true });
	}
};

