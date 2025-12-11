import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	// Join the array from rest parameter back into a string
	const featureId = params.id;
	
	try {
		// Query all dates with metadata for this feature
		const result = await db
			.prepare(
				`SELECT date, min_temp, max_temp, data_points, wtoff
         FROM temperature_metadata
         WHERE feature_id = ?
         ORDER BY date DESC`
			)
			.bind(featureId)
			.all();

		const dates = result.results?.map((r: any) => r.date) || [];
		const latestDate = dates.length > 0 ? dates[0] : null;

		return json(
			{
				dates,
				latest_date: latestDate,
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

