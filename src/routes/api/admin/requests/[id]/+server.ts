import { json } from '@sveltejs/kit';
import { getEcostressRequestDetail, getLandsatRunDetail } from '$lib/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params, url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const id = parseInt(params.id);
	if (isNaN(id)) {
		return json({ error: 'Invalid request ID' }, { status: 400 });
	}

	const source = url.searchParams.get('source') || 'ecostress';

	const detail = source === 'landsat'
		? await getLandsatRunDetail(db, id)
		: await getEcostressRequestDetail(db, id);

	if (!detail) {
		return json({ error: 'Request not found' }, { status: 404 });
	}

	return json(detail, {
		headers: {
			'cache-control': 'no-store'
		}
	});
};
