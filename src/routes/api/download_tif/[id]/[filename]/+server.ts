import type { RequestHandler } from './$types';
import { buildFeaturePath } from '$lib/db';

export const GET: RequestHandler = async ({ params, platform }) => {
	const r2 = platform?.env?.R2_DATA;
	
	if (!r2) {
		return new Response(JSON.stringify({ error: 'R2 storage not available' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}

	const key = buildFeaturePath(params.id, params.filename);
	
	try {
		const obj = await r2.get(key);
		
		if (!obj) {
			return new Response(JSON.stringify({ error: 'Not found', key }), { 
				status: 404,
				headers: { 'content-type': 'application/json' }
			});
		}

		return new Response(obj.body as BodyInit, {
			headers: {
				'content-type': 'application/octet-stream',
				'content-disposition': `attachment; filename="${params.filename}"`,
				'cache-control': 'public, max-age=300'
			}
		});
	} catch (err) {
		console.error('R2 fetch error:', err);
		return new Response(JSON.stringify({ error: 'Failed to fetch TIF' }), { 
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}
};

