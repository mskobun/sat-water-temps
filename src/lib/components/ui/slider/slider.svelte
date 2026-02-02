<script lang="ts">
	import { Slider as SliderPrimitive } from "bits-ui";
	import { cn } from "$lib/utils.js";

	let {
		ref = $bindable(null),
		value = $bindable([0]),
		class: className,
		trackClass,
		showRange = true,
		...restProps
	}: SliderPrimitive.RootProps & { trackClass?: string; showRange?: boolean } = $props();
</script>

<SliderPrimitive.Root
	bind:ref
	bind:value
	class={cn("relative flex w-full touch-none items-center select-none", className)}
	{...restProps}
>
	<span
		class={cn("relative h-2 w-full grow overflow-hidden rounded-full", trackClass || "bg-muted")}
	>
		{#if showRange}
			<SliderPrimitive.Range class="bg-primary/30 absolute h-full" />
		{/if}
	</span>
	{#each value as _, i}
		<SliderPrimitive.Thumb
			index={i}
			class="border-primary bg-background ring-ring/50 block size-4 shrink-0 rounded-full border shadow-sm transition-[color,box-shadow] hover:ring-4 focus-visible:ring-4 focus-visible:outline-hidden disabled:pointer-events-none disabled:opacity-50"
		/>
	{/each}
</SliderPrimitive.Root>
