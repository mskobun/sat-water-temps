import type { RequestHandler } from './$types';

/** Parse rest path into featureId (may contain slashes) and date. */
function parsePath(path: string): { featureId: string; date: string } | null {
	const parts = path.split('/');
	if (parts.length < 2) return null;
	const date = parts.pop()!;
	const featureId = parts.join('/');
	return { featureId, date };
}

/** Serve CSV for download using csv_path from DB. */
export const GET: RequestHandler = async ({ params, platform }) => {
	const db = platform?.env?.DB;
	const r2 = platform?.env?.R2_DATA;

	if (!db || !r2) {
		return new Response(JSON.stringify({ error: 'Service not available' }), {
			status: 500,
			headers: { 'content-type': 'application/json' }
		});
	}

	const parsed = parsePath(params.path);
	if (!parsed) {
		return new Response(JSON.stringify({ error: 'Invalid path; expected featureId/date' }), {
			status: 400,
			headers: { 'content-type': 'application/json' }
		});
	}

	const { featureId, date } = parsed;

	const meta = await db
		.prepare('SELECT csv_path FROM temperature_metadata WHERE feature_id = ? AND date = ?')
		.bind(featureId, date)
		.first();

	if (!meta?.csv_path) {
		return new Response(JSON.stringify({ error: 'Not found' }), {
			status: 404,
			headers: { 'content-type': 'application/json' }
		});
	}

	const key = String(meta.csv_path);
	const obj = await r2.get(key);
	if (!obj) {
		return new Response(JSON.stringify({ error: 'Not found', key }), {
			status: 404,
			headers: { 'content-type': 'application/json' }
		});
	}

	const filename = key.split('/').pop() ?? `${date}_filter_relative.csv`;
	return new Response(obj.body as BodyInit, {
		headers: {
			'content-type': 'text/csv',
			'content-disposition': `attachment; filename="${filename}"`,
			'cache-control': 'public, max-age=300'
		}
	});
};
