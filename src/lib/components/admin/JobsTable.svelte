<script lang="ts">
	import * as Table from '$lib/components/ui/table';
	import { Badge } from '$lib/components/ui/badge';

	interface FilterStats {
		total_pixels: number;
		histogram: Record<string, number>;
	}

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
	}: {
		jobs: Job[];
		showTaskId?: boolean;
	} = $props();

	function getStatsFromHistogram(stats: FilterStats) {
		const hist = stats.histogram;
		const valid = hist['0'] || 0;
		const filtered_qc = [1, 3, 5, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		const filtered_cloud = [2, 3, 6, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		const filtered_water = [4, 5, 6, 7].reduce((sum, i) => sum + (hist[i.toString()] || 0), 0);
		return { valid, filtered_qc, filtered_cloud, filtered_water, total: stats.total_pixels };
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
		if (filtered_cloud > 0) parts.push(`Cloud: ${((filtered_cloud / total) * 100).toFixed(1)}%`);
		if (filtered_water > 0) parts.push(`Water: ${((filtered_water / total) * 100).toFixed(1)}%`);
		return parts.join(', ');
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'success': return 'secondary';
			case 'failed': return 'destructive';
			case 'started': return 'default';
			default: return 'outline';
		}
	}
</script>

<div class="overflow-x-auto">
	<Table.Root>
		<Table.Header>
			<Table.Row>
				<Table.Head>Status</Table.Head>
				<Table.Head>Type</Table.Head>
				<Table.Head>Feature / Date</Table.Head>
				{#if showTaskId}
					<Table.Head>Task ID</Table.Head>
				{/if}
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
					<Table.Cell class="text-sm text-destructive max-w-xs truncate">
						{job.error_message || '-'}
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
