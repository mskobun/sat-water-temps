<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Label } from '$lib/components/ui/label';
	import * as Table from '$lib/components/ui/table';
	import * as Select from '$lib/components/ui/select';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

	interface FilterStats {
		total_pixels: number;
		histogram: Record<string, number>;
	}

	// Helper to compute stats from histogram
	function getStatsFromHistogram(stats: FilterStats) {
		const hist = stats.histogram;
		const valid = hist['0'] || 0;
		const filtered_qc = [1, 3, 5, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		const filtered_cloud = [2, 3, 6, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		const filtered_water = [4, 5, 6, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		return { valid, filtered_qc, filtered_cloud, filtered_water, total: stats.total_pixels };
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
		metadata: any | null;
		filter_stats: FilterStats | null;
	}

	const filterOptions = [
		{ value: 'all', label: 'All Jobs' },
		{ value: 'success', label: 'Success' },
		{ value: 'failed', label: 'Failed' },
		{ value: 'started', label: 'In Progress' }
	];

	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Jobs');
	let autoRefresh = $state(false);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	async function fetchJobs() {
		try {
			const statusParam = filter !== 'all' ? `?status=${filter}` : '';
			const response = await fetch(`/api/admin/jobs${statusParam}`);
			const data = (await response.json()) as { jobs?: Job[] };
			jobs = data.jobs || [];
			error = '';
		} catch (e) {
			error = 'Failed to fetch jobs';
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

	function formatFilterSummary(stats: FilterStats | null): string {
		if (!stats) return '-';
		const { valid, total } = getStatsFromHistogram(stats);
		const pctFiltered = total > 0 ? (((total - valid) / total) * 100).toFixed(1) : '0.0';
		return `${pctFiltered}% filtered`;
	}

	function getFilterBreakdown(stats: FilterStats | null): string {
		if (!stats) return '';
		const { filtered_qc, filtered_cloud, filtered_water, total } = getStatsFromHistogram(stats);
		if (total === 0) return '';

		const parts = [];
		if (filtered_qc > 0) parts.push(`QC: ${((filtered_qc / total) * 100).toFixed(1)}%`);
		if (filtered_cloud > 0)
			parts.push(`Cloud: ${((filtered_cloud / total) * 100).toFixed(1)}%`);
		if (filtered_water > 0)
			parts.push(`Water: ${((filtered_water / total) * 100).toFixed(1)}%`);
		return parts.join(', ');
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'success':
				return 'secondary';
			case 'failed':
				return 'destructive';
			case 'started':
				return 'default';
			default:
				return 'outline';
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			refreshInterval = setInterval(fetchJobs, 5000);
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	$effect(() => {
		if (filter) {
			fetchJobs();
		}
	});

	onMount(() => {
		fetchJobs();
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Job Status - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6">
			<h1 class="text-3xl font-bold mb-2">Processing Jobs</h1>
			<p class="text-muted-foreground">Monitor Lambda processing jobs and scraping tasks</p>
		</div>

		<Card.Card class="mb-6">
			<Card.Content class="pt-6">
				<div class="flex flex-wrap items-center justify-between gap-4">
					<div class="flex items-center gap-4">
						<Label class="text-sm font-medium">Filter:</Label>
						<Select.Root type="single" bind:value={filter}>
							<Select.Trigger class="w-44">
								{#snippet children()}
									<span data-slot="select-value">{filterLabel}</span>
								{/snippet}
							</Select.Trigger>
							<Select.Content>
								{#each filterOptions as opt}
									<Select.Item value={opt.value} label={opt.label} />
								{/each}
							</Select.Content>
						</Select.Root>
					</div>
					<div class="flex items-center gap-3">
						<Button variant={autoRefresh ? 'default' : 'secondary'} size="sm" onclick={toggleAutoRefresh}>
							{autoRefresh ? '⏸ Pause' : '▶ Auto-refresh'}
						</Button>
						<Button variant="outline" size="sm" onclick={fetchJobs} disabled={loading}>
							🔄 Refresh
						</Button>
					</div>
				</div>
			</Card.Content>
		</Card.Card>

		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			{#each [
				{ label: 'Total', count: jobs.length },
				{ label: 'Success', count: jobs.filter((j) => j.status === 'success').length },
				{ label: 'Failed', count: jobs.filter((j) => j.status === 'failed').length },
				{ label: 'In Progress', count: jobs.filter((j) => j.status === 'started').length }
			] as stat}
				<Card.Card>
					<Card.Content class="pt-6">
						<div class="text-2xl font-bold">{stat.count}</div>
						<div class="text-sm text-muted-foreground">{stat.label}</div>
					</Card.Content>
				</Card.Card>
			{/each}
		</div>

		{#if loading}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading jobs...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if jobs.length === 0}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No jobs found. Jobs will appear here once Lambda functions start running.
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
								<Table.Head>Task ID</Table.Head>
								<Table.Head>Started</Table.Head>
								<Table.Head>Duration</Table.Head>
								<Table.Head>Filters</Table.Head>
								<Table.Head>Error</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each jobs as job}
								<Table.Row
									class="cursor-pointer hover:bg-muted/50"
									onclick={() => (window.location.href = `/admin/jobs/${job.id}`)}
								>
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
									<Table.Cell class="text-sm font-mono">
										{#if job.task_id}
											<span class="text-xs">{job.task_id.slice(0, 12)}...</span>
										{:else}
											-
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatDate(job.started_at)}
									</Table.Cell>
									<Table.Cell class="text-sm">{formatDuration(job.duration_ms)}</Table.Cell>
									<Table.Cell class="text-sm">
										{#if job.filter_stats}
											<div class="font-medium">{formatFilterSummary(job.filter_stats)}</div>
											<div class="text-xs text-muted-foreground">
												{getFilterBreakdown(job.filter_stats)}
											</div>
										{:else}
											-
										{/if}
									</Table.Cell>
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
	</div>
</div>
