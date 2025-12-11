import type { RequestHandler } from './$types';

const BUCKET_PREFIX = "ECO";

function buildFeaturePath(featureId: string, suffix: string): string {
	return `${BUCKET_PREFIX}/${featureId}/lake/${suffix}`;
}

export const GET: RequestHandler = async ({ params, platform }) => {
	const r2 = platform?.env?.R2_DATA;
	
	if (!r2) {
		return new Response(JSON.stringify({ error: 'R2 storage not available' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}

	// Join the array from rest parameter back into a string
	const featureId = params.id;
	const doy = params.doy;
	const scale = params.scale;
	
	// Extract name and location from featureId (format: "name/location" or just "name")
	const [name, location = "lake"] = featureId.split("/");
	const pngKey = buildFeaturePath(featureId, `${name}_${location}_${doy}_filter_${scale}.png`);
	
	try {
		const obj = await r2.get(pngKey);
		
		if (!obj) {
			return new Response(JSON.stringify({ error: 'Not found', key: pngKey }), { 
				status: 404,
				headers: { 'content-type': 'application/json' }
			});
		}

		return new Response(obj.body, {
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

