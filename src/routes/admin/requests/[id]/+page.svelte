<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import * as Table from '$lib/components/ui/table';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

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

	interface Job {
		id: number;
		job_type: string;
		task_id: string | null;
		feature_id: string | null;
		date: string | null;
		status: string;
		started_at: number;
		completed_at: number | null;
		duration_ms: number | null;
		error_message: string | null;
		metadata: string | null;
	}

	let request = $state<EcostressRequest | null>(null);
	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let error = $state('');
	let autoRefresh = $state(false);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

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

	function formatDuration(ms: number | null) {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'success':
			case 'submitted':
			case 'processing':
				return 'default';
			case 'failed':
				return 'destructive';
			case 'started':
			case 'pending':
				return 'outline';
			default:
				return 'secondary';
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			refreshInterval = setInterval(fetchDetail, 5000);
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	let successCount = $derived(jobs.filter((j) => j.status === 'success').length);
	let failedCount = $derived(jobs.filter((j) => j.status === 'failed').length);
	let runningCount = $derived(jobs.filter((j) => j.status === 'started').length);

	onMount(() => {
		fetchDetail();
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

		{#if loading}
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
									<Badge variant={request.trigger_type === 'manual' ? 'secondary' : 'outline'}>
										{request.trigger_type}
									</Badge>
								</dd>
							</div>
							<div>
								<dt class="text-muted-foreground">Status</dt>
								<dd class="mt-0.5">
									<Badge variant={getStatusVariant(request.status)}>{request.status}</Badge>
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

			<div class="flex items-center justify-between mb-4">
				<h2 class="text-xl font-semibold">Processing Jobs</h2>
				<div class="flex items-center gap-3">
					<Button variant={autoRefresh ? 'default' : 'secondary'} size="sm" onclick={toggleAutoRefresh}>
						{autoRefresh ? 'Pause' : 'Auto-refresh'}
					</Button>
					<Button variant="outline" size="sm" onclick={fetchDetail}>
						Refresh
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
					<div class="overflow-x-auto">
						<Table.Root>
							<Table.Header>
								<Table.Row>
									<Table.Head>Status</Table.Head>
									<Table.Head>Type</Table.Head>
									<Table.Head>Feature / Date</Table.Head>
									<Table.Head>Started</Table.Head>
									<Table.Head>Duration</Table.Head>
									<Table.Head>Error</Table.Head>
								</Table.Row>
							</Table.Header>
							<Table.Body>
								{#each jobs as job}
									<Table.Row>
										<Table.Cell>
											<Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
										</Table.Cell>
										<Table.Cell class="text-sm">{job.job_type}</Table.Cell>
										<Table.Cell class="text-sm">
											{#if job.feature_id}
												<div class="font-medium">{job.feature_id}</div>
												{#if job.date}
													<div class="text-xs text-muted-foreground">{job.date}</div>
												{/if}
											{:else}
												-
											{/if}
										</Table.Cell>
										<Table.Cell class="text-sm text-muted-foreground">
											{formatDate(job.started_at)}
										</Table.Cell>
										<Table.Cell class="text-sm">{formatDuration(job.duration_ms)}</Table.Cell>
										<Table.Cell class="text-sm text-destructive max-w-xs truncate">
											{job.error_message || '-'}
										</Table.Cell>
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>
					</div>
				</Card.Card>
			{/if}
		{/if}
	</div>
</div>
