import { json } from '@sveltejs/kit';
import { AwsClient } from 'aws4fetch';
import type { RequestHandler } from './$types';

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
	const { date, description } = body as { date?: string; description?: string };

	if (!date) {
		return json({ error: 'Date is required' }, { status: 400 });
	}

	// Validate date format (YYYY-MM-DD from HTML input) and convert to MM-DD-YYYY for AppEEARS
	const dateMatch = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
	if (!dateMatch) {
		return json({ error: 'Invalid date format. Expected YYYY-MM-DD.' }, { status: 400 });
	}
	const appearsDate = `${dateMatch[2]}-${dateMatch[3]}-${dateMatch[1]}`;

	const userEmail = session.user.email || 'unknown';

	// Insert pending request into D1
	const now = Date.now();
	await db
		.prepare(`
			INSERT INTO ecostress_requests
			(trigger_type, triggered_by, description, start_date, end_date, status, created_at)
			VALUES (?, ?, ?, ?, ?, 'pending', ?)
		`)
		.bind('manual', userEmail, description || `Manual trigger for ${date}`, appearsDate, appearsDate, now)
		.run();

	// Get the inserted row ID
	const inserted = await db
		.prepare(`SELECT id FROM ecostress_requests WHERE created_at = ? AND triggered_by = ? ORDER BY id DESC LIMIT 1`)
		.bind(now, userEmail)
		.first();

	const requestId = inserted?.id;

	// Invoke the initiator Lambda via Function URL
	const lambdaUrl = platform?.env?.LAMBDA_INITIATOR_URL;
	const awsKeyId = platform?.env?.AWS_ACCESS_KEY_ID;
	const awsSecret = platform?.env?.AWS_SECRET_ACCESS_KEY;
	const awsRegion = platform?.env?.AWS_LAMBDA_REGION || 'us-west-2';

	if (!lambdaUrl || !awsKeyId || !awsSecret) {
		return json({
			id: requestId,
			warning: 'Lambda invocation credentials not configured. Request recorded but Lambda not invoked.'
		}, { status: 202 });
	}

	try {
		const aws = new AwsClient({
			accessKeyId: awsKeyId,
			secretAccessKey: awsSecret,
			region: awsRegion,
			service: 'lambda'
		});

		const lambdaPayload = {
			start_date: appearsDate,
			end_date: appearsDate,
			trigger_type: 'manual',
			triggered_by: userEmail,
			description: description || `Manual trigger for ${date}`,
			request_id: requestId
		};

		const response = await aws.fetch(lambdaUrl, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(lambdaPayload)
		});

		if (!response.ok) {
			const errorText = await response.text();
			// Update request status to failed
			await db
				.prepare(`UPDATE ecostress_requests SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?`)
				.bind(`Lambda invocation failed: ${response.status} ${errorText}`, Date.now(), requestId)
				.run();

			return json({ id: requestId, error: `Lambda invocation failed: ${response.status}` }, { status: 502 });
		}

		const result = await response.json() as { task_id?: string };

		// Lambda updates the pending ecostress_requests row directly via request_id
		return json({ id: requestId, task_id: result.task_id, message: 'Processing triggered' });
	} catch (err) {
		const errorMessage = err instanceof Error ? err.message : String(err);
		await db
			.prepare(`UPDATE ecostress_requests SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?`)
			.bind(errorMessage, Date.now(), requestId)
			.run();

		return json({ id: requestId, error: errorMessage }, { status: 500 });
	}
};
