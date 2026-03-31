import { json } from '@sveltejs/kit';
import { AwsClient } from 'aws4fetch';
import type { D1Database } from '@cloudflare/workers-types';
import type { RequestHandler } from './$types';

function parseDate(str: string): RegExpMatchArray | null {
	return str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
}

function toAppearsDate(match: RegExpMatchArray): string {
	return `${match[2]}-${match[3]}-${match[1]}`;
}

async function triggerProcessing(
	db: D1Database,
	source: 'ecostress' | 'landsat',
	startDate: string,
	endDate: string,
	description: string | undefined,
	userEmail: string
) {
	if (source === 'ecostress') {
		const startMatch = parseDate(startDate)!;
		const endMatch = parseDate(endDate)!;
		const appearsStart = toAppearsDate(startMatch);
		const appearsEnd = toAppearsDate(endMatch);
		const desc = description || `Manual ECOSTRESS scan for ${appearsStart}${appearsStart !== appearsEnd ? ` to ${appearsEnd}` : ''}`;

		const result = await db
			.prepare(`
				INSERT INTO data_requests
				(source, trigger_type, triggered_by, description, start_date, end_date, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?)
			`)
			.bind('ecostress', 'manual', userEmail, desc, appearsStart, appearsEnd, Date.now())
			.run();

		const requestId = result.meta.last_row_id;

		return {
			ids: [requestId],
			requestId,
			source,
			description: desc,
			startDate,
			endDate
		};
	} else {
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
		return {
			ids: [runId],
			runId,
			source,
			description: desc,
			startDate,
			endDate
		};
	}
}

async function markRequestError(db: D1Database, requestId: number, message: string) {
	await db
		.prepare(`UPDATE data_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
		.bind(message, Date.now(), requestId)
		.run();
}

async function invokeInitiator(
	aws: AwsClient,
	lambdaUrl: string,
	payload: Record<string, unknown>
): Promise<{ ok: true } | { ok: false; error: string }> {
	try {
		const response = await aws.fetch(lambdaUrl, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			const errorText = await response.text();
			return { ok: false, error: `Lambda failed: ${response.status} ${errorText}` };
		}
		return { ok: true };
	} catch (err) {
		return { ok: false, error: `Lambda error: ${err instanceof Error ? err.message : String(err)}` };
	}
}

function getInvokeError(result: { ok: true } | { ok: false; error: string }): string | null {
	return 'error' in result ? result.error : null;
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

	const selectedSource = source || 'ecostress';
	const result = await triggerProcessing(db, selectedSource, startDate, endDate, description, userEmail);

	// If triggerProcessing returned a Response (validation error), pass through
	if (result instanceof Response) return result;

	const { ids } = result;
	const count = ids.length;

	if (!hasLambdaCreds || !aws || !lambdaUrl) {
		const warning = selectedSource === 'ecostress'
			? 'Lambda invocation credentials not configured. ECOSTRESS scan request recorded but Lambda not invoked.'
			: 'Lambda invocation credentials not configured. Landsat scan request recorded but Lambda not invoked.';
		return json({
			count,
			successful: 0,
			failed: 0,
			ids,
			errors: [],
			warning
		}, { status: 202 });
	}

	if (selectedSource === 'ecostress') {
		const requestId = result.requestId;
		const payload = {
			start_date: result.startDate,
			end_date: result.endDate,
			trigger_type: 'manual',
			triggered_by: userEmail,
			description: result.description,
			request_id: requestId
		};

		platform?.context?.waitUntil((async () => {
			const invokeResult = await invokeInitiator(aws, lambdaUrl, payload);
			const invokeError = getInvokeError(invokeResult);
			if (invokeError) {
				await markRequestError(db, requestId, invokeError);
			}
		})());

		return json({
			count,
			successful: 0,
			failed: 0,
			ids,
			message: 'ECOSTRESS scan accepted and queued. It will continue in the background.'
		}, { status: 202 });
	}

	const payload = {
		start_date: result.startDate,
		end_date: result.endDate,
		trigger_type: 'manual',
		triggered_by: userEmail,
		description: result.description,
		run_id: result.runId
	};
	const invokeResult = await invokeInitiator(aws, lambdaUrl, payload);
	const invokeError = getInvokeError(invokeResult);

	if (invokeError) {
		await markRequestError(db, result.runId, invokeError);
		return json({
			count,
			successful: 0,
			failed: 1,
			ids,
			errors: [invokeError],
			message: 'Created Landsat scan request, but Lambda invocation failed'
		});
	}

	return json({
		count,
		successful: 1,
		failed: 0,
		ids,
		message: 'Created Landsat scan request successfully'
	});
};
