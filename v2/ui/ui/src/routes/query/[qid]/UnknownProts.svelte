<script lang="ts">
	import { Alert } from 'sveltestrap';
	import type { Readable } from 'svelte/store';
	export let prompt: string;
	export let data: Readable<readonly string[]>;
</script>

{#if $data.length !== 0}
	<Alert class="alert-warning">
		{prompt}{$data.join(', ')}
	</Alert>
{/if}
