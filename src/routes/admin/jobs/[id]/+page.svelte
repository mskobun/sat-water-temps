<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import * as Table from '$lib/components/ui/table';
	import { Progress } from '$lib/components/ui/progress';

	interface FilterStats {
		total_pixels: number;
		histogram: Record<string, number>;
	}

	// Compute all statistics from bit flag histogram
	function computeStats(stats: FilterStats) {
		const hist = stats.histogram;
		const total = stats.total_pixels;

		// Bit 0 = QC, Bit 1 = Cloud, Bit 2 = Water
		const valid = hist['0'] || 0;
		const qc_only = hist['1'] || 0;
		const cloud_only = hist['2'] || 0;
		const qc_cloud = hist['3'] || 0;
		const water_only = hist['4'] || 0;
		const qc_water = hist['5'] || 0;
		const cloud_water = hist['6'] || 0;
		const all_three = hist['7'] || 0;

		// Overlapping totals
		const filtered_by_qc = qc_only + qc_cloud + qc_water + all_three;
		const filtered_by_cloud = cloud_only + qc_cloud + cloud_water + all_three;
		const filtered_by_water = water_only + qc_water + cloud_water + all_three;
		const filtered = total - valid;

		return {
			total,
			valid,
			filtered,
			filtered_by_qc,
			filtered_by_cloud,
			filtered_by_water,
			qc_only,
			cloud_only,
			water_only,
			qc_cloud,
			qc_water,
			cloud_water,
			all_three
		};
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

	let job = $state<Job | null>(null);
	let loading = $state(true);
	let error = $state('');

	const jobId = $derived($page.params.id);
	const stats = $derived(job?.filter_stats ? computeStats(job.filter_stats) : null);

	async function fetchJob() {
		try {
			const response = await fetch(`/api/admin/jobs/${jobId}`);
			if (!response.ok) {
				throw new Error('Job not found');
			}
			const data = await response.json();
			job = data.job;
			error = '';
		} catch (e) {
			error = 'Failed to fetch job details';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(fetchJob);

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
				return 'secondary';
			case 'failed':
				return 'destructive';
			case 'started':
				return 'default';
			default:
				return 'outline';
		}
	}

	function formatNumber(n: number): string {
		return n.toLocaleString();
	}

	function calcPercent(part: number, total: number): number {
		return total > 0 ? (part / total) * 100 : 0;
	}
</script>

<div class="container mx-auto p-6 space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold">Job Details</h1>
			<p class="text-muted-foreground">Job #{jobId}</p>
		</div>
		<Button variant="outline" href="/admin/jobs">Back to Jobs</Button>
	</div>

	{#if loading}
		<Card.Card>
			<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
				<Spinner class="size-12" />
				<p class="text-muted-foreground">Loading job details...</p>
			</Card.Content>
		</Card.Card>
	{:else if error}
		<Alert variant="destructive">
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{:else if job}
		<!-- Job Information Card -->
		<Card.Card>
			<Card.Header>
				<Card.Title>Job Information</Card.Title>
			</Card.Header>
			<Card.Content class="space-y-4">
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<div>
						<p class="text-sm text-muted-foreground">Status</p>
						<Badge variant={getStatusVariant(job.status)} class="mt-1">{job.status}</Badge>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Type</p>
						<p class="font-medium">{job.job_type}</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Feature</p>
						<p class="font-medium">{job.feature_id || '-'}</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Date</p>
						<p class="font-medium">{job.date || '-'}</p>
					</div>
				</div>

				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<div>
						<p class="text-sm text-muted-foreground">Started</p>
						<p class="font-medium text-sm">{formatDate(job.started_at)}</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Completed</p>
						<p class="font-medium text-sm">
							{job.completed_at ? formatDate(job.completed_at) : '-'}
						</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Duration</p>
						<p class="font-medium">{formatDuration(job.duration_ms)}</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Task ID</p>
						<p class="font-mono text-xs">{job.task_id?.slice(0, 12) || '-'}...</p>
					</div>
				</div>

				{#if job.error_message}
					<div>
						<p class="text-sm text-muted-foreground mb-2">Error Message</p>
						<Alert variant="destructive">
							<AlertDescription class="font-mono text-xs">{job.error_message}</AlertDescription>
						</Alert>
					</div>
				{/if}
			</Card.Content>
		</Card.Card>

		<!-- Filter Statistics Card -->
		{#if stats}
			<Card.Card>
				<Card.Header>
					<Card.Title>Filter Statistics</Card.Title>
					<Card.Description>
						Pixel filtering breakdown for {job.feature_id} on {job.date}
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-6">
					<!-- Overview -->
					<div class="space-y-2">
						<div class="flex justify-between text-sm">
							<span class="text-muted-foreground">Valid Data Coverage</span>
							<span class="font-medium">
								{formatNumber(stats.valid)} / {formatNumber(stats.total)}
								pixels ({calcPercent(stats.valid, stats.total).toFixed(1)}%)
							</span>
						</div>
						<Progress value={calcPercent(stats.valid, stats.total)} class="h-3" />
					</div>

					<!-- Individual Filter Breakdown -->
					<div class="space-y-4">
						<h4 class="font-semibold text-sm">Filtered By</h4>

						<!-- QC Filter -->
						<div class="space-y-2">
							<div class="flex justify-between text-sm">
								<span class="text-muted-foreground">Quality Control (QC)</span>
								<span class="font-medium">
									{formatNumber(stats.filtered_by_qc)} pixels ({calcPercent(
										stats.filtered_by_qc,
										stats.total
									).toFixed(1)}%)
								</span>
							</div>
							<Progress value={calcPercent(stats.filtered_by_qc, stats.total)} class="h-2" />
						</div>

						<!-- Cloud Filter -->
						<div class="space-y-2">
							<div class="flex justify-between text-sm">
								<span class="text-muted-foreground">Cloud Cover</span>
								<span class="font-medium">
									{formatNumber(stats.filtered_by_cloud)} pixels ({calcPercent(
										stats.filtered_by_cloud,
										stats.total
									).toFixed(1)}%)
								</span>
							</div>
							<Progress value={calcPercent(stats.filtered_by_cloud, stats.total)} class="h-2" />
						</div>

						<!-- Water Mask Filter -->
						<div class="space-y-2">
							<div class="flex justify-between text-sm">
								<span class="text-muted-foreground">Water Mask (Non-water pixels)</span>
								<span class="font-medium">
									{formatNumber(stats.filtered_by_water)} pixels ({calcPercent(
										stats.filtered_by_water,
										stats.total
									).toFixed(1)}%)
								</span>
							</div>
							<Progress value={calcPercent(stats.filtered_by_water, stats.total)} class="h-2" />
						</div>
					</div>

					<!-- Filter Combinations -->
					<div class="space-y-4">
						<h4 class="font-semibold text-sm">Filter Combinations</h4>
						<div class="rounded-md border">
							<Table.Root>
								<Table.Header>
									<Table.Row>
										<Table.Head>Combination</Table.Head>
										<Table.Head class="text-right">Pixels</Table.Head>
										<Table.Head class="text-right">Percentage</Table.Head>
									</Table.Row>
								</Table.Header>
								<Table.Body>
									<Table.Row>
										<Table.Cell class="font-medium">QC only</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.qc_only)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.qc_only, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">Cloud only</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.cloud_only)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.cloud_only, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">Water only</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.water_only)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.water_only, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">QC + Cloud</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.qc_cloud)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.qc_cloud, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">QC + Water</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.qc_water)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.qc_water, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">Cloud + Water</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.cloud_water)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.cloud_water, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
									<Table.Row>
										<Table.Cell class="font-medium">All three (QC + Cloud + Water)</Table.Cell>
										<Table.Cell class="text-right">{formatNumber(stats.all_three)}</Table.Cell>
										<Table.Cell class="text-right">
											{calcPercent(stats.all_three, stats.total).toFixed(2)}%
										</Table.Cell>
									</Table.Row>
								</Table.Body>
							</Table.Root>
						</div>
					</div>
				</Card.Content>
			</Card.Card>
		{:else}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No filter statistics available for this job.
				</Card.Content>
			</Card.Card>
		{/if}
	{/if}
</div>
