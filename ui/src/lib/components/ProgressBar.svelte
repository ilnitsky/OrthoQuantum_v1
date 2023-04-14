<script lang="ts">
	import { Progress } from 'sveltestrap';
	import type { BackgroundColor } from 'sveltestrap/src/shared';

	export let height = '1.875rem';
	export let value = 75;
	export let max = 100;
	export let animated = true;
	export let striped = false;
	export let color: BackgroundColor | undefined = undefined;
	export let message = 'Some example message';
</script>

<div class="d-flex justify-content-center align-items-center my-3">
	<span class="position-absolute mx-auto rounded px-1" class:d-none={!message}>{message}</span>
	<Progress {value} {max} {animated} {striped} {color} class="w-100" style={`height: ${height};`} />
</div>

<style>
	span {
		color: black;
		background-color: #ffffff80;
		font-size: 0.9rem;
	}
</style>
