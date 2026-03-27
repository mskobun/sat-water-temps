<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import SourceBadge from '$lib/components/SourceBadge.svelte';
	import ThumbnailPreview from '$lib/components/ThumbnailPreview.svelte';
	import { Spinner } from '$lib/components/ui/spinner';
	import { Skeleton } from '$lib/components/ui/skeleton';
	import * as Table from '$lib/components/ui/table';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { formatDateTime } from '$lib/date-utils';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import { toast } from 'svelte-sonner';
	import type { ArchiveEntry } from '$lib/db';

	const featureId = $page.params.id;

	let entries: ArchiveEntry[] = $state([]);
	let loading = $state(true);
	let selectedDates = $state(new Set<string>());
	let sourceFilter = $state<'all' | 'ecostress' | 'landsat'>('all');
	let zipDownloading = $state(false);
	let parquetDownloading = $state(false);

	const filteredEntries = $derived(
		sourceFilter === 'all'
			? entries
			: entries.filter((e) => e.source === sourceFilter)
	);

	const allFilteredSelected = $derived(
		filteredEntries.length > 0 && filteredEntries.every((e) => selectedDates.has(e.date))
	);

	const someFilteredSelected = $derived(
		filteredEntries.some((e) => selectedDates.has(e.date)) && !allFilteredSelected
	);

	const selectedCount = $derived(selectedDates.size);

	const ecostressCount = $derived(entries.filter((e) => e.source === 'ecostress').length);
	const landsatCount = $derived(entries.filter((e) => e.source === 'landsat').length);

	function toggleSelectAll() {
		if (allFilteredSelected) {
			// Deselect all filtered
			for (const e of filteredEntries) {
				selectedDates.delete(e.date);
			}
		} else {
			// Select all filtered
			for (const e of filteredEntries) {
				selectedDates.add(e.date);
			}
		}
		selectedDates = new Set(selectedDates);
	}

	function toggleRow(date: string) {
		if (selectedDates.has(date)) {
			selectedDates.delete(date);
		} else {
			selectedDates.add(date);
		}
		selectedDates = new Set(selectedDates);
	}

	async function downloadSelectedZip() {
		if (selectedDates.size === 0) return;
		zipDownloading = true;
		const dates = [...selectedDates];
		const toastId = toast.loading(`Fetching ${dates.length} CSVs…`);

		try {
			const JSZip = (await import('jszip')).default;
			const zip = new JSZip();
			let fetched = 0;

			const results = await Promise.all(
				dates.map(async (date) => {
					const res = await fetch(`/api/download_csv/${featureId}/${date}`);
					if (!res.ok) throw new Error(`Failed to fetch CSV for ${date}`);
					const blob = await res.blob();
					fetched++;
					toast.loading(`Fetching ${fetched}/${dates.length} CSVs…`, { id: toastId });
					return { date, blob };
				})
			);

			toast.loading('Creating ZIP…', { id: toastId });
			for (const { date, blob } of results) {
				zip.file(`${featureId}_${date}.csv`, blob);
			}

			const zipBlob = await zip.generateAsync({ type: 'blob' });
			const url = URL.createObjectURL(zipBlob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${featureId}_archive.zip`;
			a.click();
			URL.revokeObjectURL(url);
			toast.success(`Downloaded ${dates.length} CSVs as ZIP`, { id: toastId });
		} catch (err) {
			console.error('ZIP download error:', err);
			toast.error('Failed to create ZIP download', { id: toastId });
		} finally {
			zipDownloading = false;
		}
	}

	async function downloadParquet() {
		parquetDownloading = true;
		try {
			const listRes = await fetch(`/api/feature/${featureId}/parquet`);
			const files: Array<{ path: string; size: number }> = await listRes.json();
			if (files.length === 0) {
				toast.error('No parquet files available for this feature');
				return;
			}

			const res = await fetch(`/api/feature/${featureId}/parquet?path=${encodeURIComponent(files[0].path)}`);
			if (!res.ok) throw new Error('Failed to fetch parquet file');
			const blob = await res.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${featureId}.parquet`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Parquet download error:', err);
			toast.error('Failed to download parquet file');
		} finally {
			parquetDownloading = false;
		}
	}

	onMount(async () => {
		try {
			const res = await fetch(`/api/feature/${featureId}/archive`);
			const data = await res.json();
			entries = data.entries || [];
		} catch (err) {
			console.error('Error loading archive:', err);
			toast.error('Failed to load archive data');
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>{featureId} Archive</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<!-- Header -->
	<header class="border-b px-6 py-5 flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold">{featureId} Archive</h1>
			{#if !loading}
				<p class="text-sm text-muted-foreground mt-1">{entries.length} observations</p>
			{/if}
		</div>
		<Button
			variant="outline"
			onclick={downloadParquet}
			disabled={parquetDownloading || loading}
		>
			{#if parquetDownloading}
				<Spinner class="size-4 mr-2" />
			{:else}
				<DownloadIcon class="size-4 mr-2" />
			{/if}
			Download Parquet
		</Button>
	</header>

	<Tooltip.Provider disableHoverableContent={false}>
	<div class="w-[95%] mx-auto py-5">
		<!-- Toolbar -->
		<div class="flex items-center justify-between mb-4 gap-4 flex-wrap">
			<div class="flex items-center gap-4">
				<div class="flex items-center gap-2">
					<Checkbox
						checked={allFilteredSelected}
						indeterminate={someFilteredSelected}
						onCheckedChange={toggleSelectAll}
						disabled={loading || filteredEntries.length === 0}
					/>
					<span class="text-sm text-muted-foreground">
						{#if selectedCount > 0}
							{selectedCount} selected
						{:else}
							Select all
						{/if}
					</span>
				</div>
				<Button
					variant="default"
					size="sm"
					onclick={downloadSelectedZip}
					disabled={selectedCount === 0 || zipDownloading}
				>
					{#if zipDownloading}
						<Spinner class="size-4 mr-2" />
						Downloading…
					{:else}
						<DownloadIcon class="size-4 mr-2" />
						Download Selected (ZIP)
					{/if}
				</Button>
			</div>

			<!-- Source filter tabs -->
			<div class="flex items-center gap-1 rounded-lg border p-1 bg-muted/50">
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {sourceFilter === 'all' ? 'bg-background shadow-sm font-medium' : 'text-muted-foreground hover:text-foreground'}"
					onclick={() => (sourceFilter = 'all')}
				>
					All ({entries.length})
				</button>
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {sourceFilter === 'ecostress' ? 'bg-background shadow-sm font-medium' : 'text-muted-foreground hover:text-foreground'}"
					onclick={() => (sourceFilter = 'ecostress')}
				>
					ECOSTRESS ({ecostressCount})
				</button>
				<button
					class="px-3 py-1 text-sm rounded-md transition-colors {sourceFilter === 'landsat' ? 'bg-background shadow-sm font-medium' : 'text-muted-foreground hover:text-foreground'}"
					onclick={() => (sourceFilter = 'landsat')}
				>
					Landsat ({landsatCount})
				</button>
			</div>
		</div>

		<!-- Table -->
		{#if loading}
			<div class="border rounded-lg">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head class="w-10"></Table.Head>
							<Table.Head class="w-14"></Table.Head>
							<Table.Head>Date</Table.Head>
							<Table.Head>Source</Table.Head>
							<Table.Head class="text-right">Points</Table.Head>
							<Table.Head class="w-24"></Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each Array(8) as _}
							<Table.Row>
								<Table.Cell><Skeleton class="size-4" /></Table.Cell>
								<Table.Cell><Skeleton class="size-10 rounded" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-32" /></Table.Cell>
								<Table.Cell><Skeleton class="h-5 w-20 rounded-full" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-12 ml-auto" /></Table.Cell>
								<Table.Cell><Skeleton class="h-4 w-16 ml-auto" /></Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{:else if filteredEntries.length === 0}
			<div class="border rounded-lg py-16 text-center text-muted-foreground">
				{#if entries.length === 0}
					No data available for this feature
				{:else}
					No {sourceFilter === 'ecostress' ? 'ECOSTRESS' : 'Landsat'} observations found
				{/if}
			</div>
		{:else}
			<div class="border rounded-lg">
				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head class="w-10"></Table.Head>
							<Table.Head class="w-14">Thumb</Table.Head>
							<Table.Head>Date</Table.Head>
							<Table.Head>Source</Table.Head>
							<Table.Head class="text-right">Points</Table.Head>
							<Table.Head class="w-24 text-right">Download</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each filteredEntries as entry (entry.date)}
							<Table.Row class={selectedDates.has(entry.date) ? 'bg-muted/50' : ''}>
								<Table.Cell>
									<Checkbox
										checked={selectedDates.has(entry.date)}
										onCheckedChange={() => toggleRow(entry.date)}
									/>
								</Table.Cell>
								<Table.Cell class="p-1">
									<ThumbnailPreview
										src={`/api/feature/${featureId}/tif/${entry.date}/relative`}
										alt={formatDateTime(entry.date)}
										href={`/feature/${encodeURIComponent(featureId)}?date=${entry.date}`}
										class="block size-10"
									/>
								</Table.Cell>
								<Table.Cell>
									<a
										href={`/feature/${encodeURIComponent(featureId)}?date=${entry.date}`}
										class="hover:underline font-medium"
									>
										{formatDateTime(entry.date)}
									</a>
								</Table.Cell>
								<Table.Cell>
									<SourceBadge source={entry.source} />
								</Table.Cell>
								<Table.Cell class="text-right tabular-nums">{entry.data_points ?? '—'}</Table.Cell>
								<Table.Cell class="text-right">
									<div class="flex items-center justify-end gap-2">
										<a
											href={`/api/feature/${featureId}/tif/${entry.date}/file`}
											download
											class="text-sm text-muted-foreground hover:text-foreground transition-colors"
										>
											TIF
										</a>
										<a
											href={`/api/download_csv/${featureId}/${entry.date}`}
											download
											class="text-sm text-muted-foreground hover:text-foreground transition-colors"
										>
											CSV
										</a>
									</div>
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</div>
		{/if}
	</div>
	</Tooltip.Provider>
</div>
