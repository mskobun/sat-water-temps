import { json } from '@sveltejs/kit';
import { AwsClient } from 'aws4fetch';
import type { D1Database } from '@cloudflare/workers-types';
import type { RequestHandler } from './$types';

const MAX_RANGE_DAYS = 60;

function parseDate(str: string): RegExpMatchArray | null {
	return str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
}

function toAppearsDate(match: RegExpMatchArray): string {
	return `${match[2]}-${match[3]}-${match[1]}`;
}

function enumerateDays(start: string, end: string): string[] {
	const days: string[] = [];
	const d = new Date(start + 'T00:00:00');
	const last = new Date(end + 'T00:00:00');
	while (d <= last) {
		days.push(d.toISOString().slice(0, 10));
		d.setDate(d.getDate() + 1);
	}
	return days;
}

async function triggerProcessing(
	db: D1Database,
	aws: AwsClient | undefined,
	lambdaUrl: string | undefined,
	source: 'ecostress' | 'landsat',
	startDate: string,
	endDate: string,
	description: string | undefined,
	userEmail: string
) {
	const days = enumerateDays(startDate, endDate);
	if (days.length > MAX_RANGE_DAYS) {
		return json({ error: `Date range too large. Maximum ${MAX_RANGE_DAYS} days.` }, { status: 400 });
	}

	if (source === 'ecostress') {
		// One request per day (ECOSTRESS behavior)
		const ids: number[] = [];
		const errors: string[] = [];
		let successful = 0;

		for (const day of days) {
			const dayMatch = parseDate(day)!;
			const appearsDate = toAppearsDate(dayMatch);
			const dayDesc = description ? `${description} (${appearsDate})` : `Manual trigger for ${appearsDate}`;

			const result = await db
				.prepare(`
					INSERT INTO data_requests
					(source, trigger_type, triggered_by, description, start_date, end_date, created_at)
					VALUES (?, ?, ?, ?, ?, ?, ?)
				`)
				.bind('ecostress', 'manual', userEmail, dayDesc, appearsDate, appearsDate, Date.now())
				.run();

			const requestId = result.meta.last_row_id;
			ids.push(requestId);

			if (!aws || !lambdaUrl) continue;

			try {
				const response = await aws.fetch(lambdaUrl, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						start_date: appearsDate,
						end_date: appearsDate,
						trigger_type: 'manual',
						triggered_by: userEmail,
						description: dayDesc,
						request_id: requestId
					})
				});

				if (!response.ok) {
					const errorText = await response.text();
					const msg = `Lambda failed for ${day}: ${response.status} ${errorText}`;
					errors.push(msg);
					await db
						.prepare(`UPDATE data_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
						.bind(msg, Date.now(), requestId)
						.run();
				} else {
					successful++;
				}
			} catch (err) {
				const msg = `Lambda error for ${day}: ${err instanceof Error ? err.message : String(err)}`;
				errors.push(msg);
				await db
					.prepare(`UPDATE data_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
					.bind(msg, Date.now(), requestId)
					.run();
			}
		}

		return { ids, errors, successful, count: days.length };
	} else {
		// One request for entire range (Landsat behavior)
		const desc = description || `Manual Landsat trigger for ${startDate} to ${endDate}`;

		const result = await db
			.prepare(`
				INSERT INTO data_requests
				(source, trigger_type, triggered_by, description, start_date, end_date, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?)
			`)
			.bind('landsat', 'manual', userEmail, desc, startDate, endDate, Date.now())
			.run();

		const runId = result.meta.last_row_id;

		if (!aws || !lambdaUrl) {
			return { ids: [runId], errors: [], successful: 0, count: 1, noLambda: true };
		}

		try {
			const response = await aws.fetch(lambdaUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					start_date: startDate,
					end_date: endDate,
					trigger_type: 'manual',
					triggered_by: userEmail,
					description: desc,
					run_id: runId
				})
			});

			if (!response.ok) {
				const errorText = await response.text();
				const msg = `Lambda failed: ${response.status} ${errorText}`;
				await db
					.prepare(`UPDATE data_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
					.bind(msg, Date.now(), runId)
					.run();
				return { ids: [runId], errors: [msg], successful: 0, count: 1 };
			}

			return { ids: [runId], errors: [], successful: 1, count: 1 };
		} catch (err) {
			const msg = `Lambda error: ${err instanceof Error ? err.message : String(err)}`;
			await db
				.prepare(`UPDATE data_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
				.bind(msg, Date.now(), runId)
				.run();
			return { ids: [runId], errors: [msg], successful: 0, count: 1 };
		}
	}
}

export const POST: RequestHandler = async ({ request, locals, platform }) => {
	const db = platform?.env?.DB;
	if (!db) {
		return json({ error: 'Database not available' }, { status: 500 });
	}

	const session = await locals.auth();
	if (!session?.user) {
		return json({ error: 'Unauthorized' }, { status: 401 });
	}

	const body = await request.json();
	const { startDate, endDate, description, source } = body as {
		startDate?: string;
		endDate?: string;
		description?: string;
		source?: 'ecostress' | 'landsat';
	};

	if (!startDate || !endDate) {
		return json({ error: 'startDate and endDate are required' }, { status: 400 });
	}

	const startMatch = parseDate(startDate);
	const endMatch = parseDate(endDate);
	if (!startMatch || !endMatch) {
		return json({ error: 'Invalid date format. Expected YYYY-MM-DD.' }, { status: 400 });
	}

	if (endDate < startDate) {
		return json({ error: 'endDate must not be before startDate' }, { status: 400 });
	}

	const userEmail = session.user.email || 'unknown';
	const isLandsat = source === 'landsat';

	const lambdaUrl = isLandsat
		? platform?.env?.LAMBDA_LANDSAT_INITIATOR_URL
		: platform?.env?.LAMBDA_INITIATOR_URL;
	const awsKeyId = platform?.env?.AWS_ACCESS_KEY_ID;
	const awsSecret = platform?.env?.AWS_SECRET_ACCESS_KEY;
	const awsRegion = platform?.env?.AWS_LAMBDA_REGION || 'us-west-2';
	const hasLambdaCreds = !!(lambdaUrl && awsKeyId && awsSecret);

	let aws: AwsClient | undefined;
	if (hasLambdaCreds) {
		aws = new AwsClient({
			accessKeyId: awsKeyId,
			secretAccessKey: awsSecret,
			region: awsRegion,
			service: 'lambda'
		});
	}

	const result = await triggerProcessing(db, aws, lambdaUrl, source || 'ecostress', startDate, endDate, description, userEmail);

	// If triggerProcessing returned a Response (validation error), pass through
	if (result instanceof Response) return result;

	const { ids, errors, successful, count } = result;
	const noLambda = 'noLambda' in result && result.noLambda;

	if (!hasLambdaCreds || noLambda) {
		return json({
			count,
			successful: 0,
			failed: 0,
			ids,
			errors: [],
			warning: 'Lambda invocation credentials not configured. Requests recorded but Lambda not invoked.'
		}, { status: 202 });
	}

	const failed = errors.length;
	const message = failed > 0
		? `Created ${count} request(s): ${successful} succeeded, ${failed} failed`
		: `Created ${count} request(s) successfully`;

	return json({
		count,
		successful,
		failed,
		ids,
		errors: errors.length > 0 ? errors : undefined,
		message
	});
};
