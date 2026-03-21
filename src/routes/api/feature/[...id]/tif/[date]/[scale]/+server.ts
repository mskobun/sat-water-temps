import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;
	
	if (!db || !r2) {
		return new Response(JSON.stringify({ error: 'Service not available' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}

	const featureId = params.id;
	const date = params.date;
	const scale = params.scale;
	
	let pngKey = "";
	try {
		const meta = await db.prepare(
			"SELECT png_path FROM temperature_metadata WHERE feature_id = ? AND date = ?"
		).bind(featureId, date).first();
		
		if (!meta?.png_path) {
			return new Response(JSON.stringify({ error: 'Metadata not found' }), { 
				status: 404,
				headers: { 'content-type': 'application/json' }
			});
		}
		
		// Append scale suffix to base path (stored without scale or extension)
		pngKey = `${meta.png_path}_${scale}.png`;
	} catch (err) {
		console.error('Error fetching metadata:', err);
		return new Response(JSON.stringify({ error: 'Database error' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}
	
	try {
		const obj = await r2.get(pngKey);
		
		if (!obj) {
			return new Response(JSON.stringify({ error: 'Not found', key: pngKey }), { 
				status: 404,
				headers: { 'content-type': 'application/json' }
			});
		}

		return new Response(obj.body as BodyInit, {
			headers: {
				'content-type': 'image/png',
				'cache-control': 'public, max-age=300'
			}
		});
	} catch (err) {
		console.error('R2 fetch error:', err);
		return new Response(JSON.stringify({ error: 'Failed to fetch image' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}
};

