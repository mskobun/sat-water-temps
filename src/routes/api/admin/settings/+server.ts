import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const { results } = await db.prepare('SELECT key, value FROM app_settings').all();
	const settings: Record<string, string> = {};
	for (const row of results) {
		settings[row.key as string] = row.value as string;
	}

	return json(settings, {
		headers: { 'cache-control': 'no-store' }
	});
};

export const PUT: RequestHandler = async ({ request, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const { key, value } = await request.json();
	if (!key || value === undefined) {
		return json({ error: 'Missing key or value' }, { status: 400 });
	}

	await db
		.prepare(
			'INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at'
		)
		.bind(key, String(value), Date.now())
		.run();

	return json({ ok: true });
};
