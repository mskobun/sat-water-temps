import { json } from '@sveltejs/kit';
import { getFeatureDetail, getJobsByFeature, countJobsByFeature } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const featureId = params.id;
	const limit = parseInt(url.searchParams.get('limit') || '50');
	const page = parseInt(url.searchParams.get('page') || '1');
	const status = url.searchParams.get('status') || undefined;
	const offset = (page - 1) * limit;

	const [feature, jobs, total] = await Promise.all([
		getFeatureDetail(db, featureId),
		getJobsByFeature(db, featureId, limit, offset, status),
		countJobsByFeature(db, featureId, status),
	]);

	if (!feature) {
		return json({ error: 'Feature not found' }, { status: 404 });
	}

	return json({ feature, jobs, total, page, limit }, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
