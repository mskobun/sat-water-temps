<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import * as Table from '$lib/components/ui/table';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

	interface Feature {
		id: string;
		name: string;
		location: string;
		latest_date: string | null;
		last_updated: number | null;
		total_jobs: number;
		success_jobs: number;
		failed_jobs: number;
		running_jobs: number;
		date_count: number;
	}

	const POLL_INTERVAL = 30_000;

	let features = $state<Feature[]>([]);
	let loading = $state(true);
	let error = $state('');
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	const totalFeatures = $derived(features.length);
	const lakeCount = $derived(features.filter((f) => f.location === 'lake').length);
	const riverCount = $derived(features.filter((f) => f.location === 'river').length);
	const withRecentData = $derived(features.filter((f) => f.date_count > 0).length);

	async function fetchFeatures() {
		try {
			const response = await fetch('/api/admin/features');
			const data = (await response.json()) as { features?: Feature[] };
			features = data.features || [];
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch features';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function formatTimestamp(ts: number | null) {
		if (!ts) return '-';
		return new Date(ts).toLocaleString();
	}

	onMount(() => {
		fetchFeatures();
		refreshInterval = setInterval(fetchFeatures, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Features - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6">
			<h1 class="text-3xl font-bold mb-2">Features</h1>
			<p class="text-muted-foreground">Water bodies monitored by the platform</p>
		</div>

		<div class="flex items-center justify-end gap-3 mb-6">
			{#if updatedAt}
				<span class="text-xs text-muted-foreground">Updated {updatedAt}</span>
			{/if}
			<Button variant="outline" size="sm" onclick={fetchFeatures} disabled={loading}>
				↻ Refresh
			</Button>
		</div>

		<!-- Stats cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			{#each [
				{ label: 'Total Features', count: totalFeatures },
				{ label: 'Lakes', count: lakeCount },
				{ label: 'Rivers', count: riverCount },
				{ label: 'With Data', count: withRecentData }
			] as stat}
				<Card.Card>
					<Card.Content class="pt-6">
						<div class="text-2xl font-bold">{stat.count}</div>
						<div class="text-sm text-muted-foreground">{stat.label}</div>
					</Card.Content>
				</Card.Card>
			{/each}
		</div>

		{#if loading && features.length === 0}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading features...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if features.length === 0}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No features found.
				</Card.Content>
			</Card.Card>
		{:else}
			<Card.Card>
				<div class="overflow-x-auto">
					<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>Name</Table.Head>
								<Table.Head>Feature ID</Table.Head>
								<Table.Head>Latest Date</Table.Head>
								<Table.Head>Dates</Table.Head>
								<Table.Head>Processing</Table.Head>
								<Table.Head>Last Updated</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each features as feature}
								<Table.Row
									class="cursor-pointer hover:bg-muted/50"
									onclick={() =>
										(window.location.href = `/admin/features/${feature.id}`)}
								>
									<Table.Cell>
										<div class="flex items-center gap-2">
											<span class="font-medium">{feature.name}</span>
											<Badge variant="outline" class="text-xs"
												>{feature.location}</Badge
											>
										</div>
									</Table.Cell>
									<Table.Cell class="font-mono text-sm">{feature.id}</Table.Cell>
									<Table.Cell class="text-sm"
										>{feature.latest_date || '-'}</Table.Cell
									>
									<Table.Cell class="text-sm">{feature.date_count}</Table.Cell>
									<Table.Cell class="text-sm">
										<span class="font-medium"
											>{feature.success_jobs}/{feature.total_jobs}</span
										>
										{#if feature.failed_jobs > 0}
											<span class="text-destructive ml-1"
												>({feature.failed_jobs} failed)</span
											>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatTimestamp(feature.last_updated)}
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
