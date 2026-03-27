<script>
	import '../app.css';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from '$lib/components/ui/sonner';
</script>

<ModeWatcher/>
<Toaster />
<slot />
