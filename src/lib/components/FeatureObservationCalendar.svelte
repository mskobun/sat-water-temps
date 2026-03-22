<script lang="ts">
	import { Calendar } from '$lib/components/ui/calendar';
	import { Button } from '$lib/components/ui/button';
	import * as Popover from '$lib/components/ui/popover';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { Calendar as CalendarPrimitive } from 'bits-ui';
	import { buttonVariants } from '$lib/components/ui/button/index.js';
	import { cn } from '$lib/utils.js';
	import { CalendarDate, type DateValue } from '@internationalized/date';
	import { compareDates, dateStringToCalendarKey, formatDateTime, parseDate, sourceLabel } from '$lib/date-utils';
	import CalendarIcon from '@lucide/svelte/icons/calendar';

	type SourceFlags = { ecostress: boolean; landsat: boolean };

	let open = $state(false);
	let pendingDayKey = $state<string | null>(null);

	let {
		selectedDate = '',
		dateEntries = [] as Array<{ date: string; source: string }>,
		featureId = '',
		colorScale = 'relative' as 'relative' | 'fixed' | 'gray',
		onSelect
	}: {
		selectedDate?: string;
		dateEntries?: Array<{ date: string; source: string }>;
		featureId?: string;
		colorScale?: 'relative' | 'fixed' | 'gray';
		onSelect: (date: string) => void;
	} = $props();

	function serverDateToCalendarValue(date: string): CalendarDate {
		const d = parseDate(date);
		return new CalendarDate(d.getFullYear(), d.getMonth() + 1, d.getDate());
	}

	function dateValueToKey(d: DateValue): string {
		return `${d.year}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
	}

	const sourcesByDay = $derived.by(() => {
		const o: Record<string, SourceFlags> = {};
		for (const e of dateEntries) {
			const key = dateStringToCalendarKey(e.date);
			const cur = o[key] ?? { ecostress: false, landsat: false };
			if (e.source === 'landsat') cur.landsat = true;
			else cur.ecostress = true;
			o[key] = cur;
		}
		return o;
	});

	function entriesForDay(key: string): Array<{ date: string; source: string }> {
		return dateEntries.filter((e) => dateStringToCalendarKey(e.date) === key);
	}

	const pendingEntries = $derived(pendingDayKey ? entriesForDay(pendingDayKey) : []);

	const bounds = $derived.by(() => {
		if (dateEntries.length === 0) {
			return { min: undefined as CalendarDate | undefined, max: undefined as CalendarDate | undefined };
		}
		let min = dateEntries[0].date;
		let max = dateEntries[0].date;
		for (const e of dateEntries) {
			if (compareDates(e.date, min) < 0) min = e.date;
			if (compareDates(e.date, max) > 0) max = e.date;
		}
		return {
			min: serverDateToCalendarValue(min),
			max: serverDateToCalendarValue(max)
		};
	});

	const calendarPlaceholder = $derived(
		selectedDate
			? serverDateToCalendarValue(selectedDate)
			: dateEntries.length > 0
				? serverDateToCalendarValue(dateEntries[0].date)
				: undefined
	);

	const calendarValue = $derived(
		selectedDate ? serverDateToCalendarValue(selectedDate) : undefined
	);

	function serverDateForCalendarKey(key: string): string | null {
		const matches = dateEntries.filter((e) => dateStringToCalendarKey(e.date) === key);
		if (matches.length === 0) return null;
		matches.sort((a, b) => compareDates(b.date, a.date));
		return matches[0].date;
	}

	function handleValueChange(v: DateValue | undefined) {
		if (!v) return;
		const key = dateValueToKey(v);
		const flags = sourcesByDay[key];
		if (!flags) return;

		// If both sources exist on this day, show the picker
		if (flags.ecostress && flags.landsat) {
			pendingDayKey = key;
			return;
		}

		// Single source — select immediately
		const server = serverDateForCalendarKey(key);
		if (server) {
			pendingDayKey = null;
			onSelect(server);
			open = false;
		}
	}

	function selectEntry(entry: { date: string; source: string }) {
		pendingDayKey = null;
		onSelect(entry.date);
		open = false;
	}

	function isDateDisabled(d: DateValue): boolean {
		return !(dateValueToKey(d) in sourcesByDay);
	}
</script>

<Popover.Root bind:open onOpenChange={(o) => { if (!o) pendingDayKey = null; }}>
	<Popover.Trigger>
		<Button
			variant="outline"
			class={cn(
				'w-full justify-start gap-2 text-left font-normal',
				!selectedDate && 'text-muted-foreground'
			)}
		>
			<CalendarIcon class="size-4 shrink-0" />
			<span class="truncate">{selectedDate ? formatDateTime(selectedDate) : 'Pick a date'}</span>
		</Button>
	</Popover.Trigger>
	<Popover.Content class="w-auto p-0" align="start">
		<div class="space-y-0">
			{#key selectedDate}
				<Calendar
					type="single"
					class="rounded-md border-0 p-2 [--cell-size:--spacing(9)]"
					value={calendarValue}
					onValueChange={handleValueChange}
					placeholder={calendarPlaceholder}
					minValue={bounds.min}
					maxValue={bounds.max}
					captionLayout="dropdown"
					weekdayFormat="short"
					isDateDisabled={isDateDisabled}
					day={day}
				/>
			{/key}
			{#if pendingDayKey && pendingEntries.length > 1}
				<div class="border-t px-3 py-2 space-y-1.5">
					<p class="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
						Select observation
					</p>
					{#each pendingEntries as entry}
						{@const isLandsat = entry.source === 'landsat'}
						<button
							type="button"
							class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-accent transition-colors"
							onclick={() => selectEntry(entry)}
						>
							<span
								class={cn(
									'w-0.5 self-stretch rounded-full shrink-0',
									isLandsat ? 'bg-blue-500' : 'bg-orange-500'
								)}
							></span>
							<div class="flex flex-col min-w-0">
								<span class="font-medium">{sourceLabel(entry.source)}</span>
								<span class="text-[10px] text-muted-foreground">{formatDateTime(entry.date)}</span>
							</div>
							{#if featureId}
								<img
									src={`/api/feature/${featureId}/tif/${entry.date}/${colorScale}`}
									alt=""
									loading="lazy"
									class="size-8 rounded object-cover bg-muted ml-auto shrink-0"
								/>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
			<div
				class="border-t px-3 py-2"
				role="group"
				aria-label="Data source legend"
			>
				<div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] text-muted-foreground">
					<span class="inline-flex items-center gap-1.5">
						<span class="size-1.5 shrink-0 rounded-full bg-orange-500" aria-hidden="true"></span>
						ECOSTRESS
					</span>
					<span class="inline-flex items-center gap-1.5">
						<span class="size-1.5 shrink-0 rounded-full bg-blue-500" aria-hidden="true"></span>
						Landsat
					</span>
				</div>
			</div>
		</div>
	</Popover.Content>
</Popover.Root>

{#snippet day({ day: date, outsideMonth: _outsideMonth }: { day: DateValue; outsideMonth: boolean })}
	{@const key = dateValueToKey(date)}
	{@const flags = sourcesByDay[key] ?? { ecostress: false, landsat: false }}
	{@const hasObs = flags.ecostress || flags.landsat}
	{@const serverDate = hasObs && featureId ? serverDateForCalendarKey(key) : null}
	{@const pngUrl = serverDate ? `/api/feature/${featureId}/tif/${serverDate}/${colorScale}` : null}
	{#if pngUrl}
		<Tooltip.Root delayDuration={200}>
			<Tooltip.Trigger>
				{@render dayCell(flags, hasObs)}
			</Tooltip.Trigger>
			<Tooltip.Content side="right" class="p-1 bg-card border shadow-lg" arrowClasses="hidden">
				<img
					src={pngUrl}
					alt="Preview for {key}"
					loading="lazy"
					class="w-48 h-48 rounded object-cover bg-muted"
				/>
			</Tooltip.Content>
		</Tooltip.Root>
	{:else}
		{@render dayCell(flags, hasObs)}
	{/if}
{/snippet}

{#snippet dayCell(flags: SourceFlags, hasObs: boolean)}
	<CalendarPrimitive.Day
		class={cn(
			buttonVariants({ variant: 'ghost' }),
			'flex size-(--cell-size) flex-col items-center justify-center gap-0.5 p-0 leading-none font-normal whitespace-nowrap select-none',
			'[&[data-today]:not([data-selected])]:bg-accent [&[data-today]:not([data-selected])]:text-accent-foreground [&[data-today][data-disabled]]:text-muted-foreground',
			'data-[selected]:bg-primary dark:data-[selected]:hover:bg-accent/50 data-[selected]:text-primary-foreground',
			'[&[data-outside-month]:not([data-selected])]:text-muted-foreground [&[data-outside-month]:not([data-selected])]:hover:text-accent-foreground',
			'data-[disabled]:text-muted-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
			'data-[unavailable]:text-muted-foreground data-[unavailable]:line-through',
			'dark:hover:text-accent-foreground',
			'focus:border-ring focus:ring-ring/50 focus:relative',
			'min-h-(--cell-size)'
		)}
	>
		{#snippet children({ day: dayNum }: { day: string })}
			<span class="flex flex-col items-center justify-center gap-0.5">
				<span>{dayNum}</span>
				{#if hasObs}
					<span class="flex min-h-[6px] flex-row justify-center gap-0.5" aria-hidden="true">
						{#if flags.ecostress}
							<span class="size-1.5 rounded-full bg-orange-500" title="ECOSTRESS"></span>
						{/if}
						{#if flags.landsat}
							<span class="size-1.5 rounded-full bg-blue-500" title="Landsat"></span>
						{/if}
					</span>
				{/if}
			</span>
		{/snippet}
	</CalendarPrimitive.Day>
{/snippet}
