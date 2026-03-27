<script lang="ts">
	import * as Tooltip from '$lib/components/ui/tooltip';

	let {
		src,
		alt = '',
		href,
		class: className = '',
	}: {
		src: string;
		alt?: string;
		href?: string;
		class?: string;
	} = $props();

	function navigate(e: MouseEvent) {
		if (href) {
			e.stopPropagation();
			window.location.href = href;
		}
	}
</script>

<Tooltip.Root delayDuration={0}>
	<Tooltip.Trigger
		onclick={navigate}
		class={className}
	>
		<img
			{src}
			{alt}
			loading="lazy"
			class="size-full rounded object-cover bg-muted"
		/>
	</Tooltip.Trigger>
	<Tooltip.Content
		side="right"
		class="p-1 bg-card border shadow-lg {href ? 'cursor-pointer' : ''}"
		arrowClasses="hidden"
		onclick={navigate}
	>
		<img
			{src}
			{alt}
			class="w-64 h-64 rounded object-cover"
		/>
		{#if href}
			<p class="text-xs text-muted-foreground text-center py-1">Click to view on map</p>
		{/if}
	</Tooltip.Content>
</Tooltip.Root>
