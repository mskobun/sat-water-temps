<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { today, getLocalTimeZone } from '@internationalized/date';
	import type { DateRange } from 'bits-ui';
	import * as Card from '$lib/components/ui/card';
	import StatBar from '$lib/components/admin/StatBar.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Table from '$lib/components/ui/table';
	import * as Select from '$lib/components/ui/select';
	import * as Popover from '$lib/components/ui/popover';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Command from '$lib/components/ui/command';
	import { RangeCalendar } from '$lib/components/ui/range-calendar';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

	const LIMIT = 50;
	const POLL_INTERVAL = 30_000;

	type Source = 'ecostress' | 'landsat';

	interface DataRequest {
		id: number;
		source: string;
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
		total_jobs: number;
		success_jobs: number;
		failed_jobs: number;
		running_jobs: number;
	}

	interface Feature {
		id: string;
		name: string;
		location: string;
	}

	const filterOptions = [
		{ value: 'all', label: 'All Requests' },
		{ value: 'pending', label: 'Pending' },
		{ value: 'submitted', label: 'Submitted' },
		{ value: 'processing', label: 'Processing' },
		{ value: 'completed', label: 'Completed' },
		{ value: 'completed_with_errors', label: 'Completed w/ Errors' },
		{ value: 'failed', label: 'Failed' }
	];

	let source = $state<Source>('ecostress');
	let requests = $state<DataRequest[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Requests');
	let page = $state(1);
	let total = $state(0);
	let statusCounts = $state({
		total: 0,
		pending: 0,
		submitted: 0,
		processing: 0,
		completed: 0,
		completed_with_errors: 0,
		failed: 0
	});
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	const totalPages = $derived(Math.max(1, Math.ceil(total / LIMIT)));
	const rangeStart = $derived((page - 1) * LIMIT + 1);
	const rangeEnd = $derived(Math.min(page * LIMIT, total));

	// Trigger dialog state — triggerSource syncs with active tab when dialog opens
	let dialogOpen = $state(false);
	let triggerSource = $state<Source>('ecostress');

	// Processing overrides — null means "use the global default from settings"
	let triggerWaterMask = $state<'native' | 'opera_dswx' | null>(null);
	let globalWaterMask = $state<'native' | 'opera_dswx'>('native');

	// Feature multiselect
	let availableFeatures = $state<Feature[]>([]);
	let featuresLoading = $state(false);
	let triggerFeatureIds = $state<string[]>([]);
	let featurePopoverOpen = $state(false);

	$effect(() => {
		if (dialogOpen) {
			triggerSource = source;
			triggerWaterMask = null; // reset to global default on each open
			triggerFeatureIds = [];
			featurePopoverOpen = false;

			// Load the current global default so we can pre-label the selector
			fetch('/api/admin/settings')
				.then((r) => r.json())
				.then((s: Record<string, string>) => {
					if (s.landsat_water_mask === 'opera_dswx' || s.landsat_water_mask === 'native') {
						globalWaterMask = s.landsat_water_mask;
					}
				})
				.catch(() => {});

			// Load features for multiselect
			featuresLoading = true;
			fetch('/api/admin/features')
				.then((r) => r.json())
				.then((d: { features?: Feature[] }) => {
					availableFeatures = d.features ?? [];
				})
				.catch(() => {})
				.finally(() => {
					featuresLoading = false;
				});
		}
	});
	let triggerDateRange = $state<DateRange>({ start: undefined, end: undefined });
	let triggerDescription = $state('');
	let triggerLoading = $state(false);
	let triggerError = $state('');
	let triggerSuccess = $state('');
	let calendarOpen = $state(false);
	let overridesOpen = $state(false);

	const dayCount = $derived(() => {
		const { start, end } = triggerDateRange;
		if (!start || !end) return 0;
		const tz = getLocalTimeZone();
		return Math.round((end.toDate(tz).getTime() - start.toDate(tz).getTime()) / 86400000) + 1;
	});

	function toggleFeature(id: string) {
		if (triggerFeatureIds.includes(id)) {
			triggerFeatureIds = triggerFeatureIds.filter((x) => x !== id);
		} else {
			triggerFeatureIds = [...triggerFeatureIds, id];
		}
	}

	function featureLabel(f: Feature): string {
		// Show location suffix only when there are multiple entries with the same name
		const sameNameCount = availableFeatures.filter((x) => x.name === f.name).length;
		return sameNameCount > 1 ? `${f.name} (${f.location})` : f.name;
	}

	async function fetchRequests() {
		try {
			const params = new URLSearchParams({ limit: String(LIMIT), page: String(page) });
			if (filter !== 'all') params.set('status', filter);
			params.set('source', source);
			const qs = params.toString();
			const response = await fetch(`/api/admin/requests?${qs}`);
			const data = (await response.json()) as {
				requests?: DataRequest[];
				total?: number;
				status_counts?: typeof statusCounts;
				page?: number;
				limit?: number;
			};
			requests = data.requests || [];
			total = data.total ?? 0;
			if (data.status_counts) statusCounts = data.status_counts;
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch requests';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function goToPage(p: number) {
		page = Math.max(1, Math.min(p, totalPages));
		fetchRequests();
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
			failed: 'Failed'
		};
		return labels[status] ?? status;
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'processing': return 'default';
			case 'completed': return 'secondary';
			case 'completed_with_errors': return 'destructive';
			case 'failed': return 'destructive';
			case 'pending': return 'outline';
			default: return 'secondary';
		}
	}

	function getTriggerVariant(type: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (type) {
			case 'manual': return 'secondary';
			default: return 'default';
		}
	}

	async function handleTrigger() {
		if (!triggerDateRange.start || !triggerDateRange.end) return;

		triggerLoading = true;
		triggerError = '';
		triggerSuccess = '';

		try {
			const requestBody: Record<string, unknown> = {
				startDate: triggerDateRange.start!.toString(),
				endDate: triggerDateRange.end!.toString(),
				description: triggerDescription || undefined,
				source: triggerSource
			};
			// Only send processingSettings for Landsat, and only when the user has
			// explicitly selected an override (null = use global default).
			if (triggerSource === 'landsat' && triggerWaterMask !== null) {
				requestBody.processingSettings = { water_mask: triggerWaterMask };
			}
			if (triggerFeatureIds.length > 0) {
				requestBody.featureIds = triggerFeatureIds;
			}
			const response = await fetch('/api/admin/trigger', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(requestBody)
			});

			const data = await response.json() as { count?: number; error?: string; warning?: string; message?: string };

			if (!response.ok) {
				triggerError = data.error || `Request failed with status ${response.status}`;
			} else if (data.warning) {
				triggerSuccess = `${data.count} request(s) recorded. ${data.warning}`;
			} else {
				triggerSuccess = data.message || `Created ${data.count} request(s)`;
				triggerDateRange = { start: undefined, end: undefined };
				triggerDescription = '';
				triggerFeatureIds = [];
				page = 1;
				fetchRequests();
				setTimeout(() => { dialogOpen = false; triggerSuccess = ''; }, 2000);
			}
		} catch (e) {
			triggerError = 'Failed to trigger processing';
			console.error(e);
		} finally {
			triggerLoading = false;
		}
	}

	function switchSource(newSource: Source) {
		source = newSource;
		filter = 'all';
		loading = true;
		requests = [];
	}

	$effect(() => {
		source;
		filter;
		untrack(() => {
			page = 1;
			fetchRequests();
		});
	});

	onMount(() => {
		refreshInterval = setInterval(fetchRequests, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Processing Requests - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-3xl font-bold mb-2">Processing Requests</h1>
				<p class="text-muted-foreground">
					{#if source === 'ecostress'}
						Track ECOSTRESS scan requests and their processing results
					{:else}
						Track Landsat scene scanning and processing runs
					{/if}
				</p>
			</div>

			<!-- Trigger Processing Dialog -->
			<Dialog.Root bind:open={dialogOpen}>
				<Dialog.Trigger>
					{#snippet children()}
						<Button>Trigger Processing</Button>
					{/snippet}
				</Dialog.Trigger>
				<Dialog.Content class="sm:max-w-md">
					<Dialog.Header>
						<Dialog.Title>Manual Processing Trigger</Dialog.Title>
						<Dialog.Description>
							{#if triggerSource === 'ecostress'}
								Run one ECOSTRESS scan for the selected date range and queue matching granules for processing.
							{:else}
								Scan for Landsat scenes in the selected date range and queue them for processing.
							{/if}
						</Dialog.Description>
					</Dialog.Header>
					<div class="flex flex-col gap-4 py-2">
						<div class="flex flex-col gap-1.5">
							<Label>Source</Label>
							<div class="flex gap-1 rounded-md border p-1">
								<button
									class="flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors {triggerSource === 'ecostress' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
									onclick={() => { triggerSource = 'ecostress'; }}
								>ECOSTRESS</button>
								<button
									class="flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors {triggerSource === 'landsat' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
									onclick={() => { triggerSource = 'landsat'; }}
								>Landsat</button>
							</div>
						</div>
						<div class="flex flex-col gap-1.5">
							<Label>Date Range</Label>
							<Popover.Root bind:open={calendarOpen}>
								<Popover.Trigger>
									{#snippet children()}
										<Button variant="outline" class="w-full justify-start text-left font-normal">
											{#if triggerDateRange.start && triggerDateRange.end}
												{triggerDateRange.start} – {triggerDateRange.end}
											{:else if triggerDateRange.start}
												{triggerDateRange.start} – …
											{:else}
												<span class="text-muted-foreground">Select date range</span>
											{/if}
										</Button>
									{/snippet}
								</Popover.Trigger>
								<Popover.Content class="w-auto p-0" align="start">
									<RangeCalendar
										bind:value={triggerDateRange}
										maxValue={today(getLocalTimeZone())}
										captionLayout="dropdown"
										onValueChange={(v) => {
											if (v.start && v.end) {
												calendarOpen = false;
											}
										}}
									/>
								</Popover.Content>
							</Popover.Root>
						</div>
						{#if triggerDateRange.start && triggerDateRange.end}
							<p class="text-sm text-muted-foreground">
								{#if triggerFeatureIds.length > 0}
									{triggerFeatureIds.length} feature(s) will be scanned for {dayCount()} day(s)
								{:else if triggerSource === 'ecostress'}
									1 ECOSTRESS scan will be created for {dayCount()} day(s)
								{:else}
									1 Landsat scan will be created for {dayCount()} day(s)
								{/if}
							</p>
						{/if}
						<div class="flex flex-col gap-1.5">
							<Label>Features</Label>
							<p class="text-xs text-muted-foreground -mt-1">Leave empty to process all features</p>
							{#if triggerFeatureIds.length > 0}
								<div class="flex flex-wrap gap-1">
									{#each triggerFeatureIds as fid}
										{@const f = availableFeatures.find((x) => x.id === fid)}
										<Badge variant="secondary" class="gap-1 pr-1">
											{f ? featureLabel(f) : fid}
											<button
												class="ml-0.5 rounded-full hover:bg-muted-foreground/20 p-0.5 leading-none"
												onclick={() => toggleFeature(fid)}
												aria-label="Remove {f?.name ?? fid}"
											>×</button>
										</Badge>
									{/each}
								</div>
							{/if}
							<Popover.Root bind:open={featurePopoverOpen}>
								<Popover.Trigger>
									{#snippet children()}
										<Button variant="outline" class="w-full justify-start font-normal" role="combobox" aria-expanded={featurePopoverOpen}>
											{#if featuresLoading}
												<Spinner class="size-3.5 mr-2" />Loading features…
											{:else if triggerFeatureIds.length === 0}
												<span class="text-muted-foreground">All features — click to filter</span>
											{:else}
												{triggerFeatureIds.length} feature{triggerFeatureIds.length === 1 ? '' : 's'} selected
											{/if}
										</Button>
									{/snippet}
								</Popover.Trigger>
								<Popover.Content class="p-0 w-72" align="start">
									<Command.Root>
										<Command.Input placeholder="Search features…" />
										<Command.Empty>No features found</Command.Empty>
										<Command.List>
											<Command.Group>
												{#each availableFeatures as f (f.id)}
													<Command.Item
														value={featureLabel(f)}
														onSelect={() => toggleFeature(f.id)}
													>
														<span class="mr-2 w-3.5 shrink-0">
															{triggerFeatureIds.includes(f.id) ? '✓' : ''}
														</span>
														{featureLabel(f)}
													</Command.Item>
												{/each}
											</Command.Group>
										</Command.List>
									</Command.Root>
								</Popover.Content>
							</Popover.Root>
						</div>
						<div class="flex flex-col gap-1.5">
							<Label for="trigger-desc">Description (optional)</Label>
							<Input
								id="trigger-desc"
								type="text"
								placeholder="e.g. Re-process after cloud clearing"
								bind:value={triggerDescription}
							/>
						</div>
						{#if triggerSource === 'landsat'}
							<div class="border rounded-md">
								<button
									class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors"
									onclick={() => { overridesOpen = !overridesOpen; }}
								>
									<span>Processing overrides</span>
									<span class="text-muted-foreground text-xs">{overridesOpen ? '▲' : '▼'}</span>
								</button>
								{#if overridesOpen}
									<div class="px-3 pb-3 pt-1 flex flex-col gap-2 border-t">
										<div class="flex flex-col gap-1.5">
											<Label class="text-xs text-muted-foreground">Water mask</Label>
											<div class="flex gap-1 rounded-md border p-1 w-fit">
												<button
													class="rounded px-2.5 py-1 text-xs font-medium transition-colors {triggerWaterMask === null ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
													onclick={() => { triggerWaterMask = null; }}
												>Default ({globalWaterMask === 'opera_dswx' ? 'OPERA' : 'Native'})</button>
												<button
													class="rounded px-2.5 py-1 text-xs font-medium transition-colors {triggerWaterMask === 'native' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
													onclick={() => { triggerWaterMask = 'native'; }}
												>Native</button>
												<button
													class="rounded px-2.5 py-1 text-xs font-medium transition-colors {triggerWaterMask === 'opera_dswx' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
													onclick={() => { triggerWaterMask = 'opera_dswx'; }}
												>OPERA DSWx-HLS</button>
											</div>
										</div>
									</div>
								{/if}
							</div>
						{/if}
						{#if triggerError}
							<Alert variant="destructive">
								<AlertDescription>{triggerError}</AlertDescription>
							</Alert>
						{/if}
						{#if triggerSuccess}
							<Alert>
								<AlertDescription>{triggerSuccess}</AlertDescription>
							</Alert>
						{/if}
					</div>
					<Dialog.Footer>
						<Button variant="outline" onclick={() => { dialogOpen = false; }}>Cancel</Button>
						<Button onclick={handleTrigger} disabled={triggerLoading || !triggerDateRange.start || !triggerDateRange.end}>
							{#if triggerLoading}
								<Spinner class="size-4 mr-2" />
							{/if}
							Submit
						</Button>
					</Dialog.Footer>
				</Dialog.Content>
			</Dialog.Root>
		</div>

		<!-- Source tabs -->
		<div class="flex gap-1 rounded-md border p-1 w-fit mb-6">
			<button
				class="rounded px-4 py-1.5 text-sm font-medium transition-colors {source === 'ecostress' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
				onclick={() => switchSource('ecostress')}
			>ECOSTRESS</button>
			<button
				class="rounded px-4 py-1.5 text-sm font-medium transition-colors {source === 'landsat' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
				onclick={() => switchSource('landsat')}
			>Landsat</button>
		</div>

		<!-- Lightweight filter toolbar -->
		<div class="flex flex-wrap items-center justify-between gap-4 mb-6">
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
				{#if updatedAt}
					<span class="text-xs text-muted-foreground">Updated {updatedAt}</span>
				{/if}
				<Button variant="outline" size="sm" onclick={fetchRequests} disabled={loading}>
					↻ Refresh
				</Button>
			</div>
		</div>

		<div class="mb-6">
			<StatBar stats={[
				{ label: 'Total', count: statusCounts.total },
				{ label: 'Pending', count: statusCounts.pending },
				{ label: 'Processing', count: statusCounts.processing },
				{ label: 'Completed', count: statusCounts.completed },
				{ label: 'Failed', count: statusCounts.failed + statusCounts.completed_with_errors }
			]} />
		</div>

		{#if loading && requests.length === 0}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading requests...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if requests.length === 0}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No requests found. Requests will appear here once the pipeline runs or you trigger one manually.
				</Card.Content>
			</Card.Card>
		{:else}
			<div class="overflow-x-auto rounded-md border">
				<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>Trigger</Table.Head>
								<Table.Head>Status</Table.Head>
								<Table.Head>Date Range</Table.Head>
								<Table.Head>Description</Table.Head>
								<Table.Head>Scenes</Table.Head>
								<Table.Head>Processing</Table.Head>
								<Table.Head>Created</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each requests as r}
								<Table.Row
									class="cursor-pointer hover:bg-muted/50"
									onclick={() => goto(`/admin/requests/${r.id}?source=${source}`)}
								>
									<Table.Cell>
										<Badge variant={getTriggerVariant(r.trigger_type)}>{r.trigger_type}</Badge>
									</Table.Cell>
									<Table.Cell>
										<Badge variant={getStatusVariant(r.status)}>{formatStatus(r.status)}</Badge>
									</Table.Cell>
									<Table.Cell class="text-sm">
										<div>{r.start_date}</div>
										{#if r.start_date !== r.end_date}
											<div class="text-xs text-muted-foreground">to {r.end_date}</div>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm max-w-xs truncate">
										{r.description || '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{r.scenes_count ?? '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{#if r.total_jobs > 0}
											<div>
												<span class="text-green-600 font-medium">{r.success_jobs}</span>
												<span class="text-muted-foreground"> / {r.total_jobs}</span>
											</div>
											{#if r.failed_jobs > 0}
												<div class="text-xs text-destructive">{r.failed_jobs} failed</div>
											{/if}
											{#if r.running_jobs > 0}
												<div class="text-xs text-blue-600">{r.running_jobs} running</div>
											{/if}
										{:else}
											<span class="text-muted-foreground">-</span>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatDate(r.created_at)}
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>

					<!-- Pagination controls -->
					<div class="flex items-center justify-between px-4 py-3 border-t text-sm">
						<span class="text-muted-foreground">
							Showing {rangeStart}-{rangeEnd} of {total}
						</span>
						<div class="flex items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								onclick={() => goToPage(page - 1)}
								disabled={page <= 1}
							>
								Prev
							</Button>
							<span class="text-muted-foreground">Page {page} of {totalPages}</span>
							<Button
								variant="outline"
								size="sm"
								onclick={() => goToPage(page + 1)}
								disabled={page >= totalPages}
							>
								Next
							</Button>
						</div>
					</div>
				</div>
		{/if}
	</div>
</div>
