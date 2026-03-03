<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, untrack } from 'svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { Label } from '$lib/components/ui/label';
	import * as Select from '$lib/components/ui/select';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import JobsTable from '$lib/components/admin/JobsTable.svelte';
	import type { Job } from '$lib/components/admin/JobsTable.svelte';
	import { format } from 'date-fns';

	const LIMIT = 50;
	const POLL_INTERVAL = 30_000;

	const filterOptions = [
		{ value: 'all', label: 'All Jobs' },
		{ value: 'success', label: 'Success' },
		{ value: 'failed', label: 'Failed' },
		{ value: 'started', label: 'In Progress' }
	];

	interface Feature {
		id: string;
		name: string;
		location: string;
		latest_date: string | null;
		last_updated: number | null;
		last_success_at: number | null;
		total_jobs: number;
		success_jobs: number;
		failed_jobs: number;
		running_jobs: number;
		date_count: number;
	}

	let featureId = $derived($page.params.id);
	let feature = $state<Feature | null>(null);
	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Jobs');
	let jobPage = $state(1);
	let total = $state(0);
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	const totalPages = $derived(Math.max(1, Math.ceil(total / LIMIT)));
	const rangeStart = $derived((jobPage - 1) * LIMIT + 1);
	const rangeEnd = $derived(Math.min(jobPage * LIMIT, total));

	async function fetchData() {
		try {
			const params = new URLSearchParams({ limit: String(LIMIT), page: String(jobPage) });
			if (filter !== 'all') params.set('status', filter);
			const response = await fetch(`/api/admin/features/${featureId}?${params}`);
			if (!response.ok) {
				error = response.status === 404 ? 'Feature not found' : 'Failed to fetch feature';
				return;
			}
			const data = (await response.json()) as {
				feature?: Feature;
				jobs?: Job[];
				total?: number;
			};
			feature = data.feature || null;
			jobs = data.jobs || [];
			total = data.total ?? 0;
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch feature';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function goToPage(p: number) {
		jobPage = Math.max(1, Math.min(p, totalPages));
		fetchData();
	}

	$effect(() => {
		filter;
		untrack(() => {
			jobPage = 1;
			fetchData();
		});
	});

	function formatShortDate(ts: number | null) {
		if (!ts) return '-';
		return format(new Date(ts), 'd MMM yyyy');
	}


	onMount(() => {
		refreshInterval = setInterval(fetchData, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>{feature?.name || featureId} - Features - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<!-- Back link -->
		<a
			href="/admin/features"
			class="text-sm text-muted-foreground hover:text-foreground mb-4 inline-block"
		>
			← Back to Features
		</a>

		{#if loading && !feature}
			<div class="flex flex-col items-center justify-center py-12 gap-4">
				<Spinner class="size-12" />
				<p class="text-muted-foreground">Loading feature...</p>
			</div>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if feature}
			<!-- Row 1: Title -->
			<div class="flex items-center justify-between mb-1">
				<div class="flex items-center gap-3">
					<h1 class="text-3xl font-bold">{feature.name}</h1>
					<Badge variant="outline">{feature.location}</Badge>
				</div>
				<Button variant="outline" size="sm" href="/feature/{feature.id}">
					View on map →
				</Button>
			</div>

			<!-- Row 2: Subtitle -->
			<p class="text-sm text-muted-foreground mb-4">
				{feature.id} · {feature.date_count} dates · Updated {formatShortDate(feature.last_success_at)}
			</p>

			<!-- Row 3: Stats + toolbar -->
			<div class="flex flex-wrap items-center justify-between gap-4 mb-4">
				<div class="flex items-center gap-5">
					{#each [
						{ label: 'total', count: feature.total_jobs },
						{ label: 'success', count: feature.success_jobs },
						{ label: 'failed', count: feature.failed_jobs },
						{ label: 'running', count: feature.running_jobs }
					] as stat}
						<span class="text-sm">
							<span class="font-bold">{stat.count}</span>
							<span class="text-muted-foreground">{stat.label}</span>
						</span>
					{/each}
				</div>
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
					{#if updatedAt}
						<span class="text-xs text-muted-foreground">Updated {updatedAt}</span>
					{/if}
					<Button variant="outline" size="sm" onclick={fetchData} disabled={loading}>
						↻
					</Button>
				</div>
			</div>

			<!-- Jobs table -->
			{#if jobs.length === 0}
				<Card.Card>
					<Card.Content class="py-12 text-center text-muted-foreground">
						No jobs found for this feature.
					</Card.Content>
				</Card.Card>
			{:else}
				<div class="rounded-md border">
					<JobsTable {jobs} showTaskId={true} showFeatureId={false} />

					<div class="flex items-center justify-between px-4 py-3 border-t text-sm">
						<span class="text-muted-foreground">
							Showing {rangeStart}–{rangeEnd} of {total}
						</span>
						<div class="flex items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								onclick={() => goToPage(jobPage - 1)}
								disabled={jobPage <= 1}
							>
								← Prev
							</Button>
							<span class="text-muted-foreground">
								Page {jobPage} of {totalPages}
							</span>
							<Button
								variant="outline"
								size="sm"
								onclick={() => goToPage(jobPage + 1)}
								disabled={jobPage >= totalPages}
							>
								Next →
							</Button>
						</div>
					</div>
				</div>
			{/if}
		{/if}
	</div>
</div>
