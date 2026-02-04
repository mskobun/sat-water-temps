<script lang="ts">
	import { goto } from '$app/navigation';
	import * as Command from '$lib/components/ui/command';
	import * as Kbd from '$lib/components/ui/kbd';

	let { geojsonData }: { geojsonData: any } = $props();

	let query = $state('');
	let focused = $state(false);
	let inputRef: HTMLInputElement | null = $state(null);

	let allFeatures = $derived.by(() => {
		if (!geojsonData?.features) return [];
		return geojsonData.features
			.map((f: any) => {
				const name = f.properties.name;
				const location = f.properties.location || 'lake';
				const id = location === 'lake' ? name : `${name}/${location}`;
				return { name, location, id };
			})
			.sort((a, b) => {
				// Sort by name first, then lakes before rivers
				const nameCompare = a.name.localeCompare(b.name);
				if (nameCompare !== 0) return nameCompare;
				return a.location === 'lake' ? -1 : 1;
			});
	});

	let showDropdown = $derived(focused && query.trim().length > 0);

	function selectFeature(featureId: string) {
		goto(`/feature/${encodeURIComponent(featureId)}`, {
			replaceState: false,
			keepFocus: true,
			noScroll: true
		});
		query = '';
		focused = false;
		inputRef?.blur();
	}

	function handleGlobalKeydown(e: KeyboardEvent) {
		if (e.key === '/' && !isInputFocused()) {
			e.preventDefault();
			inputRef?.focus();
		}
	}

	function isInputFocused(): boolean {
		const el = document.activeElement;
		return (
			el instanceof HTMLInputElement ||
			el instanceof HTMLTextAreaElement ||
			(el instanceof HTMLElement && el.isContentEditable)
		);
	}
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

<div class="absolute top-4 left-4 z-40 w-72 max-w-[calc(100%-2rem)]">
	<Command.Root class="rounded-lg border shadow-md backdrop-blur-sm bg-background/80" shouldFilter={true}>
		<div class="relative">
			<Command.Input
				placeholder="Search features..."
				bind:value={query}
				bind:ref={inputRef}
				onfocus={() => (focused = true)}
				onblur={() => {
					setTimeout(() => {
						focused = false;
					}, 150);
				}}
			/>
			{#if !focused && !query}
				<Kbd.Root class="absolute right-2 top-1/2 -translate-y-1/2">/</Kbd.Root>
			{/if}
		</div>
		{#if showDropdown}
			<Command.List>
				<Command.Empty>No water bodies found.</Command.Empty>
				<Command.Group>
					{#each allFeatures as feature}
						<Command.Item
							value={`${feature.name} ${feature.location}`}
							onSelect={() => selectFeature(feature.id)}
						>
							<span>{feature.name}</span>
							<span class="text-xs text-muted-foreground ml-auto">{feature.location}</span>
						</Command.Item>
					{/each}
				</Command.Group>
			</Command.List>
		{/if}
	</Command.Root>
</div>
