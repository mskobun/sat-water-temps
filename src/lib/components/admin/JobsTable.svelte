<script lang="ts">
	import * as Table from '$lib/components/ui/table';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { Badge } from '$lib/components/ui/badge';
	import ThumbnailPreview from '$lib/components/ThumbnailPreview.svelte';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import CircleOffIcon from '@lucide/svelte/icons/circle-off';
	import { format } from 'date-fns';
	import { formatShortDate as formatDateShort } from '$lib/date-utils';
	import { parseFilterStats, type FilterStats } from '$lib/filter-stats';

	export interface Job {
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

	let {
		jobs,
		showTaskId = true,
		showFeatureId = true,
	}: {
		jobs: Job[];
		showTaskId?: boolean;
		showFeatureId?: boolean;
	} = $props();

	function formatDate(timestamp: number) {
		return format(new Date(timestamp), 'dd/MM/yyyy HH:mm:ss');
	}

	function formatJobDate(dateStr: string) {
		return formatDateShort(dateStr);
	}

	function formatDuration(ms: number | null) {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	function formatFilterSummary(stats: FilterStats | null): string {
		if (!stats) return '-';
		const { valid, total } = parseFilterStats(stats);
		const pctFiltered = total > 0 ? (((total - valid) / total) * 100).toFixed(1) : '0.0';
		return `${pctFiltered}% filtered`;
	}

	function getFilterBreakdown(stats: FilterStats | null): string {
		if (!stats) return '';
		const { filtered_by_qc, filtered_by_cloud, filtered_by_water, filtered_by_nodata, total } = parseFilterStats(stats);
		if (total === 0) return '';
		const parts = [];
		if (filtered_by_nodata > 0) parts.push(`NoData: ${((filtered_by_nodata / total) * 100).toFixed(1)}%`);
		if (filtered_by_qc > 0) parts.push(`QC: ${((filtered_by_qc / total) * 100).toFixed(1)}%`);
		if (filtered_by_cloud > 0) parts.push(`Cloud: ${((filtered_by_cloud / total) * 100).toFixed(1)}%`);
		if (filtered_by_water > 0) parts.push(`Water: ${((filtered_by_water / total) * 100).toFixed(1)}%`);
		return parts.join(', ');
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'success': return 'secondary';
			case 'failed': return 'destructive';
			case 'started': return 'default';
			case 'nodata': return 'outline';
			default: return 'outline';
		}
	}
</script>

<Tooltip.Provider disableHoverableContent={false}>
<div class="overflow-x-auto">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head class="w-14"></Table.Head>
				<Table.Head>Status</Table.Head>
				<Table.Head>Type</Table.Head>
				<Table.Head>{showFeatureId ? 'Feature / Date' : 'Date'}</Table.Head>
				{#if showTaskId}
					<Table.Head>Task ID</Table.Head>
				{/if}
				<Table.Head>Started</Table.Head>
				<Table.Head>Duration</Table.Head>
				<Table.Head>Filters</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each jobs as job}
				<Table.Row
					class="cursor-pointer hover:bg-muted/50"
					onclick={() => (window.location.href = `/admin/jobs/${job.id}`)}
				>
					<Table.Cell class="p-1">
						{#if job.status === 'success' && job.feature_id && job.date}
							<ThumbnailPreview
								src="/api/feature/{job.feature_id}/tif/{job.date}/relative"
								alt="{job.date}"
								href="/feature/{job.feature_id}?date={job.date}"
								class="block w-12 h-12"
							/>
						{:else if job.status === 'nodata'}
							<Tooltip.Root delayDuration={0}>
								<Tooltip.Trigger>
									<div class="w-12 h-12 rounded bg-muted flex items-center justify-center">
										<CircleOffIcon class="size-5 text-muted-foreground" />
									</div>
								</Tooltip.Trigger>
								<Tooltip.Content side="right" class="max-w-sm">
									<p class="text-sm">No valid pixels after filtering</p>
								</Tooltip.Content>
							</Tooltip.Root>
						{:else if job.status === 'failed'}
							<Tooltip.Root delayDuration={0}>
								<Tooltip.Trigger>
									<div class="w-12 h-12 rounded bg-muted flex items-center justify-center">
										<TriangleAlertIcon class="size-5 text-destructive" />
									</div>
								</Tooltip.Trigger>
								<Tooltip.Content side="right" class="max-w-sm">
									<p class="text-sm">{job.error_message || 'Unknown error'}</p>
								</Tooltip.Content>
							</Tooltip.Root>
						{:else}
							<div class="w-12 h-12"></div>
						{/if}
					</Table.Cell>
					<Table.Cell>
						<Badge variant={getStatusVariant(job.status)}>{job.status}</Badge>
					</Table.Cell>
					<Table.Cell class="text-sm">{job.job_type}</Table.Cell>
					<Table.Cell class="text-sm">
						{#if showFeatureId && job.feature_id}
							<a href="/admin/features/{job.feature_id}" class="font-medium hover:underline" onclick={(e: MouseEvent) => e.stopPropagation()}>{job.feature_id}</a>
							{#if job.date}
								<div class="text-xs text-muted-foreground">{formatJobDate(job.date)}</div>
							{/if}
						{:else if job.date}
							<div>{formatJobDate(job.date)}</div>
						{:else}
							-
						{/if}
					</Table.Cell>
					{#if showTaskId}
						<Table.Cell class="text-sm font-mono">
							{#if job.task_id}
								<span class="text-xs">{job.task_id.slice(0, 12)}...</span>
							{:else}
								-
							{/if}
						</Table.Cell>
					{/if}
					<Table.Cell class="text-sm text-muted-foreground">
						{formatDate(job.started_at)}
					</Table.Cell>
					<Table.Cell class="text-sm">{formatDuration(job.duration_ms)}</Table.Cell>
					<Table.Cell class="text-sm">
						{#if job.filter_stats}
							<div class="font-medium">{formatFilterSummary(job.filter_stats)}</div>
							<div class="text-xs text-muted-foreground">{getFilterBreakdown(job.filter_stats)}</div>
						{:else}
							-
						{/if}
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
</Tooltip.Provider>
