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
	const { request_id } = body as { request_id?: number };

	if (!request_id) {
		return json({ error: 'request_id is required' }, { status: 400 });
	}

	// Fetch the original request
	const originalRequest = await db
		.prepare(`SELECT * FROM ecostress_requests WHERE id = ?`)
		.bind(request_id)
		.first();

	if (!originalRequest) {
		return json({ error: 'Request not found' }, { status: 404 });
	}

	// Validate that task_id exists
	if (!originalRequest.task_id) {
		return json({
			error: 'Cannot reprocess: request has no task_id. The original request may not have completed submission to AppEEARS.'
		}, { status: 400 });
	}

	const taskId = String(originalRequest.task_id);

	// Check if there's already an active reprocessing job for this task_id
	// Status is computed via the ecostress_requests_with_status view
	const activeReprocess = await db
		.prepare(`
			SELECT id, status
			FROM ecostress_requests_with_status
			WHERE task_id = ?
			AND trigger_type = 'reprocess'
			AND status IN ('submitted', 'processing', 'pending')
			LIMIT 1
		`)
		.bind(taskId)
		.first();

	if (activeReprocess) {
		return json({
			error: 'A reprocessing job is already active for this task. Please wait for it to complete.'
		}, { status: 409 });
	}

	const userEmail = session.user.email || 'unknown';

	// Create new ecostress_request row for the reprocessing
	const now = Date.now();
	const description = `Reprocess of request #${request_id} (${originalRequest.description || 'no description'})`;

	await db
		.prepare(`
			INSERT INTO ecostress_requests
			(task_id, trigger_type, triggered_by, description, start_date, end_date, created_at)
			VALUES (?, 'reprocess', ?, ?, ?, ?, ?)
		`)
		.bind(
			taskId,
			userEmail,
			description,
			originalRequest.start_date,
			originalRequest.end_date,
			now
		)
		.run();

	// Get the inserted row ID
	const inserted = await db
		.prepare(`SELECT id FROM ecostress_requests WHERE created_at = ? AND triggered_by = ? ORDER BY id DESC LIMIT 1`)
		.bind(now, userEmail)
		.first();

	const newRequestId = inserted?.id;

	// Invoke Step Functions directly
	const stepFunctionArn = platform?.env?.STEP_FUNCTION_ARN;
	const awsKeyId = platform?.env?.AWS_ACCESS_KEY_ID;
	const awsSecret = platform?.env?.AWS_SECRET_ACCESS_KEY;
	const awsRegion = platform?.env?.AWS_LAMBDA_REGION || 'us-west-2';

	if (!stepFunctionArn || !awsKeyId || !awsSecret) {
		return json({
			id: newRequestId,
			warning: 'Step Function credentials not configured. Request recorded but Step Function not invoked.'
		}, { status: 202 });
	}

	try {
		const aws = new AwsClient({
			accessKeyId: awsKeyId,
			secretAccessKey: awsSecret,
			region: awsRegion,
			service: 'states'
		});

		// Invoke Step Functions with task_id and wait_seconds=0 (immediate processing)
		const sfnInput = {
			task_id: taskId,
			wait_seconds: 0
		};

		// Construct Step Functions API endpoint
		const sfnEndpoint = `https://states.${awsRegion}.amazonaws.com`;

		const response = await aws.fetch(sfnEndpoint, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-amz-json-1.0',
				'X-Amz-Target': 'AWSStepFunctions.StartExecution'
			},
			body: JSON.stringify({
				stateMachineArn: stepFunctionArn,
				input: JSON.stringify(sfnInput)
			})
		});

		if (!response.ok) {
			const errorText = await response.text();

			// Update request with error message (status is computed dynamically)
			await db
				.prepare(`UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
				.bind(`Step Function invocation failed: ${response.status} ${errorText}`, Date.now(), newRequestId)
				.run();

			return json({
				id: newRequestId,
				error: `Step Function invocation failed: ${response.status}`
			}, { status: 502 });
		}

		const result = await response.json() as { executionArn?: string };

		// Update timestamp (status is computed dynamically from processing_jobs)
		await db
			.prepare(`UPDATE ecostress_requests SET updated_at = ? WHERE id = ?`)
			.bind(Date.now(), newRequestId)
			.run();

		return json({
			id: newRequestId,
			task_id: taskId,
			execution_arn: result.executionArn,
			message: 'Reprocessing started'
		});

	} catch (err) {
		const errorMessage = err instanceof Error ? err.message : String(err);
		// Update with error message (status is computed dynamically)
		await db
			.prepare(`UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE id = ?`)
			.bind(errorMessage, Date.now(), newRequestId)
			.run();

		return json({ id: newRequestId, error: errorMessage }, { status: 500 });
	}
};
