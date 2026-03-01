<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import JobsTable from '$lib/components/admin/JobsTable.svelte';
	import type { Job } from '$lib/components/admin/JobsTable.svelte';

	const POLL_INTERVAL = 30_000;

	interface EcostressRequest {
		id: number;
		task_id: string | null;
		trigger_type: string;
		triggered_by: string | null;
		description: string | null;
		start_date: string;
		end_date: string;
		status: string;
		scenes_count: number | null;
		created_at: number;
		updated_at: number | null;
		error_message: string | null;
	}

	let request = $state<EcostressRequest | null>(null);
	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let error = $state('');
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	// Reprocess state
	let reprocessLoading = $state(false);
	let reprocessError = $state('');
	let reprocessSuccess = $state('');

	async function fetchDetail() {
		try {
			const response = await fetch(`/api/admin/requests/${$page.params.id}`);
			if (!response.ok) {
				error = response.status === 404 ? 'Request not found' : 'Failed to fetch request';
				return;
			}
			const data = (await response.json()) as { request: EcostressRequest; jobs: Job[] };
			request = data.request;
			jobs = data.jobs || [];
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch request details';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function formatDate(timestamp: number) {
		return new Date(timestamp).toLocaleString();
	}

	function formatStatus(status: string): string {
		const labels: Record<string, string> = {
			pending: 'Pending',
			submitted: 'Submitted',
			processing: 'Processing',
			completed: 'Completed',
			completed_with_errors: 'Completed with Errors',
			failed: 'Failed',
			started: 'Started',
			success: 'Success'
		};
		return labels[status] ?? status;
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'processing': return 'default';
			case 'completed': return 'secondary';
			case 'completed_with_errors': return 'destructive';
			case 'failed': return 'destructive';
			case 'started':
			case 'pending': return 'outline';
			default: return 'secondary';
		}
	}

	async function handleReprocess() {
		if (!request?.task_id) return;

		reprocessLoading = true;
		reprocessError = '';
		reprocessSuccess = '';

		try {
			const response = await fetch('/api/admin/reprocess', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ request_id: request.id })
			});

			const result = await response.json();

			if (!response.ok) {
				reprocessError = result.error || 'Failed to start reprocessing';
				return;
			}

			reprocessSuccess = `Reprocessing started! New request ID: ${result.id}`;
			await fetchDetail();
		} catch (e) {
			reprocessError = 'Failed to start reprocessing';
			console.error(e);
		} finally {
			reprocessLoading = false;
		}
	}

	let successCount = $derived(jobs.filter((j) => j.status === 'success').length);
	let failedCount = $derived(jobs.filter((j) => j.status === 'failed').length);
	let runningCount = $derived(jobs.filter((j) => j.status === 'started').length);

	onMount(() => {
		fetchDetail();
		refreshInterval = setInterval(fetchDetail, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Request #{$page.params.id} - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6">
			<a href="/admin/requests" class="text-sm text-muted-foreground hover:text-foreground mb-2 inline-block">
				&larr; Back to Requests
			</a>
			<h1 class="text-3xl font-bold">Request #{$page.params.id}</h1>
		</div>

		{#if loading && !request}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading request...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if request}
			<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
				<Card.Card class="lg:col-span-2">
					<Card.Header>
						<Card.Title>Request Details</Card.Title>
					</Card.Header>
					<Card.Content>
						<dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
							<div>
								<dt class="text-muted-foreground">Trigger Type</dt>
								<dd class="mt-0.5">
									<Badge variant={
										request.trigger_type === 'manual' ? 'secondary' :
										request.trigger_type === 'reprocess' ? 'outline' :
										'default'
									}>
										{request.trigger_type}
									</Badge>
								</dd>
							</div>
							<div>
								<dt class="text-muted-foreground">Status</dt>
								<dd class="mt-0.5">
									<Badge variant={getStatusVariant(request.status)}>{formatStatus(request.status)}</Badge>
								</dd>
							</div>
							<div>
								<dt class="text-muted-foreground">Triggered By</dt>
								<dd class="mt-0.5 font-medium">{request.triggered_by || '-'}</dd>
							</div>
							<div>
								<dt class="text-muted-foreground">Date Range</dt>
								<dd class="mt-0.5 font-medium">
									{request.start_date}
									{#if request.start_date !== request.end_date}
										&ndash; {request.end_date}
									{/if}
								</dd>
							</div>
							<div class="col-span-2">
								<dt class="text-muted-foreground">Description</dt>
								<dd class="mt-0.5">{request.description || '-'}</dd>
							</div>
							{#if request.task_id}
								<div class="col-span-2">
									<dt class="text-muted-foreground">AppEEARS Task ID</dt>
									<dd class="mt-0.5 font-mono text-xs">{request.task_id}</dd>
								</div>
							{/if}
							<div>
								<dt class="text-muted-foreground">Created</dt>
								<dd class="mt-0.5">{formatDate(request.created_at)}</dd>
							</div>
							{#if request.updated_at}
								<div>
									<dt class="text-muted-foreground">Last Updated</dt>
									<dd class="mt-0.5">{formatDate(request.updated_at)}</dd>
								</div>
							{/if}
							{#if request.error_message}
								<div class="col-span-2">
									<dt class="text-muted-foreground">Error</dt>
									<dd class="mt-0.5 text-destructive">{request.error_message}</dd>
								</div>
							{/if}
						</dl>
					</Card.Content>
				</Card.Card>

				<Card.Card>
					<Card.Header>
						<Card.Title>Processing Summary</Card.Title>
					</Card.Header>
					<Card.Content>
						<dl class="space-y-3 text-sm">
							<div>
								<dt class="text-muted-foreground">Scenes</dt>
								<dd class="text-2xl font-bold">{request.scenes_count ?? '-'}</dd>
							</div>
							<div>
								<dt class="text-muted-foreground">Total Jobs</dt>
								<dd class="text-2xl font-bold">{jobs.length}</dd>
							</div>
							<div class="flex gap-4">
								<div>
									<dt class="text-muted-foreground">Success</dt>
									<dd class="text-lg font-bold text-green-600">{successCount}</dd>
								</div>
								<div>
									<dt class="text-muted-foreground">Failed</dt>
									<dd class="text-lg font-bold text-destructive">{failedCount}</dd>
								</div>
								<div>
									<dt class="text-muted-foreground">Running</dt>
									<dd class="text-lg font-bold text-blue-600">{runningCount}</dd>
								</div>
							</div>
						</dl>
					</Card.Content>
				</Card.Card>
			</div>

			{#if request.task_id}
				<div class="mb-6">
					<Card.Card>
						<Card.Header>
							<Card.Title>Reprocess Data</Card.Title>
							<Card.Description>
								Re-run the processing pipeline for this task without resubmitting to AppEEARS.
							</Card.Description>
						</Card.Header>
						<Card.Content>
							{#if reprocessSuccess}
								<Alert variant="default" class="mb-4">
									<AlertDescription>{reprocessSuccess}</AlertDescription>
								</Alert>
							{/if}
							{#if reprocessError}
								<Alert variant="destructive" class="mb-4">
									<AlertDescription>{reprocessError}</AlertDescription>
								</Alert>
							{/if}
							<Button
								onclick={handleReprocess}
								disabled={reprocessLoading}
								variant="outline"
							>
								{reprocessLoading ? 'Starting...' : 'Reprocess Task'}
							</Button>
						</Card.Content>
					</Card.Card>
				</div>
			{/if}

			<div class="flex items-center justify-between mb-4">
				<h2 class="text-xl font-semibold">Processing Jobs</h2>
				<div class="flex items-center gap-3">
					{#if updatedAt}
						<span class="text-xs text-muted-foreground">Updated {updatedAt}</span>
					{/if}
					<Button variant="outline" size="sm" onclick={fetchDetail}>
						↻ Refresh
					</Button>
				</div>
			</div>

			{#if jobs.length === 0}
				<Card.Card>
					<Card.Content class="py-12 text-center text-muted-foreground">
						No processing jobs yet. Jobs will appear once the pipeline starts processing scenes.
					</Card.Content>
				</Card.Card>
			{:else}
				<Card.Card>
					<JobsTable {jobs} showTaskId={false} />
				</Card.Card>
			{/if}
		{/if}
	</div>
</div>
