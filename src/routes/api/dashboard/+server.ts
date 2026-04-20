import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export type DashboardFeature = {
	feature_id: string;
	name: string;
	location: string;
	latest_date: string | null;
	observation_count: number;
	latest_mean_temp: number | null;
	latest_min_temp: number | null;
	latest_max_temp: number | null;
	latest_source: string | null;
	prev_mean_temp: number | null;
	days_since_observation: number | null;
	recent_means: number[];
};

export const GET: RequestHandler = async ({ platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	try {
		// Get all features with their latest and previous observation stats in one query
		const result = await db
			.prepare(`
				WITH ranked AS (
					SELECT
						tm.feature_id,
						tm.date,
						tm.mean_temp,
						tm.min_temp,
						tm.max_temp,
						tm.source,
						ROW_NUMBER() OVER (PARTITION BY tm.feature_id ORDER BY tm.date DESC) as rn
					FROM temperature_metadata tm
				),
				recent AS (
					SELECT
						feature_id,
						json_group_array(mean_temp) as recent_means_json
					FROM (
						SELECT feature_id, mean_temp, rn FROM ranked WHERE rn <= 10 ORDER BY feature_id, rn
					)
					GROUP BY feature_id
				)
				SELECT
					f.id as feature_id,
					f.name,
					f.location,
					f.latest_date,
					(SELECT COUNT(*) FROM temperature_metadata tm WHERE tm.feature_id = f.id) as observation_count,
					r1.mean_temp as latest_mean_temp,
					r1.min_temp as latest_min_temp,
					r1.max_temp as latest_max_temp,
					r1.source as latest_source,
					r2.mean_temp as prev_mean_temp,
					rec.recent_means_json as recent_means_json
				FROM features f
				LEFT JOIN ranked r1 ON r1.feature_id = f.id AND r1.rn = 1
				LEFT JOIN ranked r2 ON r2.feature_id = f.id AND r2.rn = 2
				LEFT JOIN recent rec ON rec.feature_id = f.id
				ORDER BY f.name
			`)
			.all();

		const now = Date.now();
		const features: DashboardFeature[] = (result.results || []).map((r: any) => {
			const latestDate = r.latest_date ? String(r.latest_date) : null;
			let daysSince: number | null = null;
			if (latestDate) {
				const d = new Date(latestDate.substring(0, 10));
				daysSince = Math.floor((now - d.getTime()) / (1000 * 60 * 60 * 24));
			}

			const num = (v: unknown) =>
				v != null && v !== '' && !Number.isNaN(Number(v)) ? Number(v) : null;

			let recent_means: number[] = [];
			if (r.recent_means_json) {
				try {
					const parsed = JSON.parse(String(r.recent_means_json));
					if (Array.isArray(parsed)) {
						recent_means = parsed.filter((v): v is number => typeof v === 'number');
					}
				} catch {
					recent_means = [];
				}
			}

			return {
				feature_id: String(r.feature_id),
				name: String(r.name),
				location: String(r.location || 'lake'),
				latest_date: latestDate,
				observation_count: Number(r.observation_count || 0),
				latest_mean_temp: num(r.latest_mean_temp),
				latest_min_temp: num(r.latest_min_temp),
				latest_max_temp: num(r.latest_max_temp),
				latest_source: r.latest_source ? String(r.latest_source) : null,
				prev_mean_temp: num(r.prev_mean_temp),
				days_since_observation: daysSince,
				recent_means,
			};
		});

		return json(
			{ features },
			{
				headers: {
					'cache-control': 'public, max-age=300',
				},
			}
		);
	} catch (err) {
		console.error('Dashboard query error:', err);
		return json({ error: 'Database error' }, { status: 500 });
	}
};
