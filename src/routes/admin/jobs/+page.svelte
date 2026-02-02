<script lang="ts">
	import { onMount } from 'svelte';

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

	let jobs: Job[] = [];
	let loading = true;
	let error = '';
	let filter = 'all';
	let autoRefresh = false;
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	async function fetchJobs() {
		try {
			const statusParam = filter !== 'all' ? `?status=${filter}` : '';
			const response = await fetch(`/api/admin/jobs${statusParam}`);
			const data = await response.json() as { jobs?: Job[] };
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

	function getStatusClasses(status: string) {
		switch (status) {
			case 'success':
				return 'bg-green-500/20 text-green-400';
			case 'failed':
				return 'bg-red-500/20 text-red-400';
			case 'started':
				return 'bg-yellow-500/20 text-yellow-400';
			default:
				return 'bg-gray-500/20 text-gray-400';
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			refreshInterval = setInterval(fetchJobs, 5000); // Refresh every 5s
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	$: if (filter) {
		fetchJobs();
	}

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

<div class="min-h-screen bg-dark-bg font-poppins text-white">
	<div class="container mx-auto p-6 max-w-7xl">
		<!-- Header -->
		<div class="mb-6">
			<h1 class="text-3xl font-bold text-white mb-2">Processing Jobs</h1>
			<p class="text-gray-400">Monitor Lambda processing jobs and scraping tasks</p>
		</div>

		<!-- Filters and Actions -->
		<div class="bg-dark-surface rounded-lg shadow-lg p-4 mb-6 flex flex-wrap items-center justify-between gap-4">
			<div class="flex items-center gap-4">
				<label for="filter-select" class="text-sm font-medium text-gray-300">Filter:</label>
				<select
					id="filter-select"
					bind:value={filter}
					class="bg-dark-card border border-gray-600 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan"
				>
					<option value="all">All Jobs</option>
					<option value="success">Success</option>
					<option value="failed">Failed</option>
					<option value="started">In Progress</option>
				</select>
			</div>

			<div class="flex items-center gap-3">
				<button
					onclick={toggleAutoRefresh}
					class="px-4 py-2 text-sm font-medium rounded-md transition-colors {autoRefresh
						? 'bg-cyan text-dark-bg hover:bg-cyan/80'
						: 'bg-gray-700 text-gray-300 hover:bg-gray-600'}"
				>
					{autoRefresh ? '⏸ Pause' : '▶ Auto-refresh'}
				</button>

				<button
					onclick={fetchJobs}
					disabled={loading}
					class="px-4 py-2 text-sm font-medium bg-dark-card border border-gray-600 text-gray-300 rounded-md hover:bg-gray-700 disabled:opacity-50 transition-colors"
				>
					🔄 Refresh
				</button>
			</div>
		</div>

		<!-- Stats -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			{#each [
				{ label: 'Total', count: jobs.length, bgColor: 'bg-blue-500/10', textColor: 'text-blue-400' },
				{ label: 'Success', count: jobs.filter((j) => j.status === 'success').length, bgColor: 'bg-green-500/10', textColor: 'text-green-400' },
				{ label: 'Failed', count: jobs.filter((j) => j.status === 'failed').length, bgColor: 'bg-red-500/10', textColor: 'text-red-400' },
				{ label: 'In Progress', count: jobs.filter((j) => j.status === 'started').length, bgColor: 'bg-yellow-500/10', textColor: 'text-yellow-400' }
			] as stat}
				<div class="rounded-lg shadow-lg p-4 {stat.bgColor} border border-gray-700/50">
					<div class="text-2xl font-bold {stat.textColor}">{stat.count}</div>
					<div class="text-sm text-gray-400">{stat.label}</div>
				</div>
			{/each}
		</div>

		<!-- Jobs Table -->
		{#if loading}
			<div class="bg-dark-surface rounded-lg shadow-lg p-12 text-center">
				<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan mx-auto mb-4"></div>
				<p class="text-gray-400">Loading jobs...</p>
			</div>
		{:else if error}
			<div class="bg-red-500/10 border border-red-500/50 rounded-lg p-4 text-red-400">
				{error}
			</div>
		{:else if jobs.length === 0}
			<div class="bg-dark-surface rounded-lg shadow-lg p-12 text-center text-gray-500">
				No jobs found. Jobs will appear here once Lambda functions start running.
			</div>
		{:else}
			<div class="bg-dark-surface rounded-lg shadow-lg overflow-hidden">
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-gray-700">
						<thead class="bg-dark-card">
							<tr>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Status</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Type</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Feature / Date</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Task ID</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Started</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Duration</th>
								<th class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Error</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-gray-700">
							{#each jobs as job}
								<tr class="hover:bg-gray-800/50 transition-colors">
									<td class="px-6 py-4 whitespace-nowrap">
										<span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full {getStatusClasses(job.status)}">
											{job.status}
										</span>
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
										{job.job_type}
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
										{#if job.feature_id}
											<div class="font-medium text-white">{job.feature_id}</div>
											{#if job.date}
												<div class="text-xs text-gray-500">{job.date}</div>
											{/if}
										{:else}
											-
										{/if}
									</td>
									<td class="px-6 py-4 text-sm text-gray-500 font-mono">
										{#if job.task_id}
											<span class="text-xs">{job.task_id.slice(0, 12)}...</span>
										{:else}
											-
										{/if}
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
										{formatDate(job.started_at)}
									</td>
									<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
										{formatDuration(job.duration_ms)}
									</td>
									<td class="px-6 py-4 text-sm text-red-400 max-w-xs truncate">
										{job.error_message || '-'}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	</div>
</div>
