import type { RequestHandler } from './$types';

/** Serve raw TIF file for download (path from DB). */
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
	const doy = params.doy;

	const meta = await db
		.prepare('SELECT tif_path FROM temperature_metadata WHERE feature_id = ? AND date = ?')
		.bind(featureId, doy)
		.first();

	if (!meta?.tif_path) {
		return new Response(JSON.stringify({ error: 'Not found' }), {
			status: 404,
			headers: { 'content-type': 'application/json' }
		});
	}

	const key = String(meta.tif_path);
	const obj = await r2.get(key);
	if (!obj) {
		return new Response(JSON.stringify({ error: 'Not found', key }), {
			status: 404,
			headers: { 'content-type': 'application/json' }
		});
	}

	const filename = key.split('/').pop() ?? `${doy}_filter_relative.tif`;
	return new Response(obj.body as BodyInit, {
		headers: {
			'content-type': 'application/octet-stream',
			'content-disposition': `attachment; filename="${filename}"`,
			'cache-control': 'public, max-age=300'
		}
	});
};
