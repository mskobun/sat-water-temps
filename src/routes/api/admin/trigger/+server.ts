import { json } from '@sveltejs/kit';
import { AwsClient } from 'aws4fetch';
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
	const { startDate, endDate, description } = body as {
		startDate?: string;
		endDate?: string;
		description?: string;
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

	const days = enumerateDays(startDate, endDate);
	if (days.length > MAX_RANGE_DAYS) {
		return json({ error: `Date range too large. Maximum ${MAX_RANGE_DAYS} days.` }, { status: 400 });
	}

	const userEmail = session.user.email || 'unknown';

	const lambdaUrl = platform?.env?.LAMBDA_INITIATOR_URL;
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

	const ids: number[] = [];
	const errors: string[] = [];
	let successful = 0;

	for (const day of days) {
		const dayMatch = parseDate(day)!;
		const appearsDate = toAppearsDate(dayMatch);
		const dayDesc = description ? `${description} (${appearsDate})` : `Manual trigger for ${appearsDate}`;

		// Insert request row
		const result = await db
			.prepare(`
				INSERT INTO ecostress_requests
				(trigger_type, triggered_by, description, start_date, end_date, created_at)
				VALUES (?, ?, ?, ?, ?, ?)
			`)
			.bind('manual', userEmail, dayDesc, appearsDate, appearsDate, Date.now())
			.run();

		const requestId = result.meta.last_row_id;
		ids.push(requestId);

		if (!aws) continue;

		try {
			const lambdaPayload = {
				start_date: appearsDate,
				end_date: appearsDate,
				trigger_type: 'manual',
				triggered_by: userEmail,
				description: dayDesc,
				request_id: requestId
			};

			const response = await aws.fetch(lambdaUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(lambdaPayload)
			});

			if (!response.ok) {
				const errorText = await response.text();
				const msg = `Lambda failed for ${day}: ${response.status} ${errorText}`;
				errors.push(msg);
				await db
					.prepare(`UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
					.bind(msg, Date.now(), requestId)
					.run();
			} else {
				successful++;
			}
		} catch (err) {
			const msg = `Lambda error for ${day}: ${err instanceof Error ? err.message : String(err)}`;
			errors.push(msg);
			await db
				.prepare(`UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
				.bind(msg, Date.now(), requestId)
				.run();
		}
	}

	if (!hasLambdaCreds) {
		return json({
			count: days.length,
			successful: 0,
			failed: 0,
			ids,
			errors: [],
			warning: 'Lambda invocation credentials not configured. Requests recorded but Lambda not invoked.'
		}, { status: 202 });
	}

	const failed = errors.length;
	const message = failed > 0
		? `Created ${days.length} request(s): ${successful} succeeded, ${failed} failed`
		: `Created ${days.length} request(s) successfully`;

	return json({
		count: days.length,
		successful,
		failed,
		ids,
		errors: errors.length > 0 ? errors : undefined,
		message
	});
};
