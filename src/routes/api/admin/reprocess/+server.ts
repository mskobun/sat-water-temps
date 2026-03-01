import { json } from '@sveltejs/kit';
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

	// Check if the request is older than 30 days (AppEEARS sample retention limit)
	const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;
	const requestAge = Date.now() - Number(originalRequest.created_at);
	if (requestAge > THIRTY_DAYS_MS) {
		return json({
			error: 'Cannot reprocess: this request is older than 30 days. AppEEARS sample data is no longer available. Please submit a new processing request instead.'
		}, { status: 400 });
	}

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

	return json({
		id: newRequestId,
		task_id: taskId,
		message: 'Reprocessing queued. The task poller will pick it up shortly.'
	});
};
