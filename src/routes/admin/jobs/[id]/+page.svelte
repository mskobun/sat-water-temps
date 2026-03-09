<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import { Progress } from '$lib/components/ui/progress';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import CircleHelpIcon from '@lucide/svelte/icons/circle-help';
	import MapIcon from '@lucide/svelte/icons/map';
	import * as Table from '$lib/components/ui/table';
	import { parseFilterStats, getFilterCombinations, type FilterStats } from '$lib/filter-stats';

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
	const stats = $derived(job?.filter_stats ? parseFilterStats(job.filter_stats) : null);
	const combinations = $derived(job?.filter_stats ? getFilterCombinations(job.filter_stats) : []);

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
		{#if job?.status === 'success' && job.feature_id && job.date}
			<Button variant="outline" href="/feature/{job.feature_id}?date={job.date}">
				<MapIcon class="size-4 mr-2" />
				View on Map
			</Button>
		{/if}
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
				<div class="flex gap-6">
					{#if job.status === 'success' && job.feature_id && job.date}
						<a href="/feature/{job.feature_id}?date={job.date}" class="shrink-0 self-start">
							<img
								src="/api/feature/{job.feature_id}/tif/{job.date}/relative"
								alt="{job.feature_id} {job.date}"
								class="w-28 h-28 rounded-md border object-cover bg-muted hover:ring-2 hover:ring-ring transition-all"
							/>
						</a>
					{/if}
					<div class="flex-1 space-y-4">
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
								<p class="font-mono text-xs break-all">{job.task_id || '-'}</p>
							</div>
						</div>
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
		<Tooltip.Provider>
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
								<span class="text-muted-foreground inline-flex items-center gap-1">
									Quality Control (QC)
									<Tooltip.Root>
										<Tooltip.Trigger>
											<CircleHelpIcon class="size-3.5 text-muted-foreground/60" />
										</Tooltip.Trigger>
										<Tooltip.Content side="right" class="max-w-xs text-xs">
											Pixels with invalid ECOSTRESS QC flags (e.g. 15, 2501, 65535).
											<a href="https://lpdaac.usgs.gov/documents/423/ECO2_User_Guide_V1.pdf" target="_blank" rel="noopener" class="underline ml-1">ECOSTRESS QC docs</a>
										</Tooltip.Content>
									</Tooltip.Root>
								</span>
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
								<span class="text-muted-foreground inline-flex items-center gap-1">
									Cloud Cover
									<Tooltip.Root>
										<Tooltip.Trigger>
											<CircleHelpIcon class="size-3.5 text-muted-foreground/60" />
										</Tooltip.Trigger>
										<Tooltip.Content side="right" class="max-w-xs text-xs">
											Pixels flagged as cloud-contaminated by the ECOSTRESS cloud mask layer.
											<a href="https://www.earthdata.nasa.gov/data/catalog/lpcloud-eco-l2-cloud-002" target="_blank" rel="noopener" class="underline ml-1">ECO_L2_CLOUD product</a>
										</Tooltip.Content>
									</Tooltip.Root>
								</span>
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
								<span class="text-muted-foreground inline-flex items-center gap-1">
									Water Mask (Non-water pixels)
									<Tooltip.Root>
										<Tooltip.Trigger>
											<CircleHelpIcon class="size-3.5 text-muted-foreground/60" />
										</Tooltip.Trigger>
										<Tooltip.Content side="right" class="max-w-xs text-xs">
											Non-water pixels removed using the ECOSTRESS water body detection layer (wt != 1).
											<a href="https://www.earthdata.nasa.gov/data/catalog/lpcloud-eco-l2-lste-002" target="_blank" rel="noopener" class="underline ml-1">ECO_L2_LSTE product</a>
										</Tooltip.Content>
									</Tooltip.Root>
								</span>
								<span class="font-medium">
									{formatNumber(stats.filtered_by_water)} pixels ({calcPercent(
										stats.filtered_by_water,
										stats.total
									).toFixed(1)}%)
								</span>
							</div>
							<Progress value={calcPercent(stats.filtered_by_water, stats.total)} class="h-2" />
						</div>

						<!-- NoData / Swath Coverage -->
						{#if stats.filtered_by_nodata > 0}
							<div class="space-y-2">
								<div class="flex justify-between text-sm">
									<span class="text-muted-foreground inline-flex items-center gap-1">
										NoData (Outside swath)
										<Tooltip.Root>
											<Tooltip.Trigger>
												<CircleHelpIcon class="size-3.5 text-muted-foreground/60" />
											</Tooltip.Trigger>
											<Tooltip.Content side="right" class="max-w-xs text-xs">
												Pixels inside the polygon with no LST data — the satellite swath did not cover this part of the water body during this overpass.
												<a href="https://www.earthdata.nasa.gov/data/instruments/ecostress" target="_blank" rel="noopener" class="underline ml-1">ECOSTRESS instrument</a>
											</Tooltip.Content>
										</Tooltip.Root>
									</span>
									<span class="font-medium">
										{formatNumber(stats.filtered_by_nodata)} pixels ({calcPercent(
											stats.filtered_by_nodata,
											stats.total
										).toFixed(1)}%)
									</span>
								</div>
								<Progress value={calcPercent(stats.filtered_by_nodata, stats.total)} class="h-2" />
							</div>
						{/if}
					</div>

					<!-- Filter Combinations -->
					{#if combinations.length > 0}
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
										{#each combinations as combo}
											<Table.Row>
												<Table.Cell class="font-medium">{combo.label}</Table.Cell>
												<Table.Cell class="text-right">{formatNumber(combo.count)}</Table.Cell>
												<Table.Cell class="text-right">{combo.pct.toFixed(2)}%</Table.Cell>
											</Table.Row>
										{/each}
									</Table.Body>
								</Table.Root>
							</div>
						</div>
					{/if}
					</Card.Content>
			</Card.Card>
		{:else}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No filter statistics available for this job.
				</Card.Content>
			</Card.Card>
		{/if}
		</Tooltip.Provider>
	{/if}
</div>
