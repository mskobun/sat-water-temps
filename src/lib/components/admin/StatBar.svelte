<script lang="ts">
	interface Stat {
		label: string;
		count: number | string;
	}

	let { stats }: { stats: Stat[] } = $props();
</script>

<div class="flex items-center gap-6 text-sm">
	{#each stats as stat, i}
		{#if i > 0}<span class="text-border">|</span>{/if}
		<div class="flex items-center gap-1.5">
			<span class="font-semibold">{stat.count}</span>
			<span class="text-muted-foreground">{stat.label}</span>
		</div>
	{/each}
</div>
