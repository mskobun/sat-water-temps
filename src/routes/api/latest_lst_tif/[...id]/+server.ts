import { getLatestDate } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;

	if (!db || !r2) {
		return new Response('Service unavailable', { status: 500 });
	}

	const featureId = params.id;

	// Get latest date from D1
	const latestDate = await getLatestDate(db, featureId);
	if (!latestDate) {
		return new Response('Not found', { status: 404 });
	}

	// Get the stored png_path directly from database
	const meta = await db.prepare(
		"SELECT png_path FROM temperature_metadata WHERE feature_id = ? AND date = ?"
	).bind(featureId, latestDate).first();
	
	if (!meta?.png_path) {
		return new Response('Not found', { status: 404 });
	}

	const obj = await r2.get(String(meta.png_path));
	if (!obj) {
		return new Response('Not found', { status: 404 });
	}

	return new Response(obj.body, {
		headers: {
			'content-type': 'image/png',
			'cache-control': 'public, max-age=300'
		}
	});
};

