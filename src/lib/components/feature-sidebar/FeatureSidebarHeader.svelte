<script lang="ts">
	import SourceBadge from '$lib/components/SourceBadge.svelte';
	import { Button } from '$lib/components/ui/button';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { formatShortDate } from '$lib/date-utils';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import SettingsIcon from '@lucide/svelte/icons/settings';

	export let featureId: string;
	export let selectedDate: string = '';
	export let dataSource: string = '';
	export let observationCount: number = 0;
	export let showAdminActions: boolean = false;
</script>

<div class="flex items-center justify-between gap-2">
	<p class="text-sm text-muted-foreground flex items-center gap-1.5 flex-wrap">
		<span>{observationCount} observation{observationCount === 1 ? '' : 's'}</span>
		{#if selectedDate}
			<span>· {formatShortDate(selectedDate)}</span>
		{/if}
		{#if dataSource}
			<SourceBadge source={dataSource} />
		{/if}
	</p>
	<Tooltip.Provider>
		<div class="flex items-center gap-1 shrink-0">
			{#if showAdminActions}
				<Tooltip.Root>
					<Tooltip.Trigger>
						<Button variant="ghost" size="icon-sm" href={`/admin/features/${featureId}`}>
							<SettingsIcon class="size-3.5" />
							<span class="sr-only">Manage in admin</span>
						</Button>
					</Tooltip.Trigger>
					<Tooltip.Content>Manage in admin</Tooltip.Content>
				</Tooltip.Root>
			{/if}
			<Tooltip.Root>
				<Tooltip.Trigger>
					<Button variant="ghost" size="icon-sm" href={`/archive/${featureId}`}>
						<DownloadIcon class="size-3.5" />
						<span class="sr-only">Archive & download</span>
					</Button>
				</Tooltip.Trigger>
				<Tooltip.Content>Archive & download</Tooltip.Content>
			</Tooltip.Root>
		</div>
	</Tooltip.Provider>
</div>
