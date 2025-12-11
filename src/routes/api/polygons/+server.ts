import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ platform }) => {
	const r2 = platform?.env?.R2_DATA;
	
	if (!r2) {
		return json({ error: 'R2 storage not available' }, { status: 500 });
	}

	try {
		// Get polygons GeoJSON from R2
		const object = await r2.get('static/polygons_new.geojson');
		
		if (!object) {
			return json({ error: 'Polygons not found' }, { status: 404 });
		}

		const geojson = await object.json();

		return json(geojson, {
			headers: {
				'content-type': 'application/geo+json',
				'cache-control': 'public, max-age=3600'
			}
		});
	} catch (err) {
		console.error('Error fetching polygons:', err);
		return json({ error: 'Failed to fetch polygons' }, { status: 500 });
	}
};
