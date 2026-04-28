import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const settingValidators: Record<string, (value: unknown) => string | null> = {
	data_delay_days: (value) => validateIntSetting(value, 0, 30),
	catchup_enabled: (value) => validateBooleanSetting(value),
	catchup_overlap_days: (value) => validateIntSetting(value, 0, 30),
	catchup_max_days: (value) => validateIntSetting(value, 1, 90),
	landsat_water_mask: (value) =>
		['native', 'opera_dswx'].includes(String(value)) ? String(value) : null
};

function validateIntSetting(value: unknown, min: number, max: number): string | null {
	const parsed = Number.parseInt(String(value), 10);
	if (!Number.isFinite(parsed) || String(parsed) !== String(value).trim()) return null;
	if (parsed < min || parsed > max) return null;
	return String(parsed);
}

function validateBooleanSetting(value: unknown): string | null {
	if (value === true || value === 'true') return 'true';
	if (value === false || value === 'false') return 'false';
	return null;
}

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
	const validator = settingValidators[String(key)];
	if (!validator) {
		return json({ error: 'Unknown setting' }, { status: 400 });
	}
	const normalizedValue = validator(value);
	if (normalizedValue === null) {
		return json({ error: 'Invalid setting value' }, { status: 400 });
	}

	await db
		.prepare(
			'INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at'
		)
		.bind(String(key), normalizedValue, Date.now())
		.run();

	return json({ ok: true });
};
