<script lang="ts" context="module">
	export function getPage<T>(data: readonly T[], page: number, pageSize: number): readonly T[] {
		return data.slice(Math.max((page - 1) * pageSize, 0), Math.min(page * pageSize, data.length));
	}
</script>

<script lang="ts">
	import { Button, InputGroup } from 'sveltestrap';

	export let page: number;
	export let pageSize: number;
	export let itemCount: number;
	$: if (!pageSize || pageSize < 1) {
		pageSize = 1;
	}

	// Minimum number of pages to show the paginator
	// 0 - show always
	// 1 - show if there is at least one item of data
	// 2 - show if there are more than one page of data
	export let minPageCountToShow: 0 | 1 | 2 = 0;
	// Minimum number of pages to show the "<<" (go to first page) and ">>" (go to last page)
	export let minPageCountForFirstLast: number | null = null;

	$: max = Math.max(1, Math.ceil(itemCount / pageSize));

	let inputValue: number;

	// On page or max change - validate page
	$: {
		if (!page || page < 1) {
			page = 1;
		} else if (page > max) {
			page = max;
		}
		inputValue = page;
	}

	$: width = max.toString().length + 3;
</script>

{#if max >= minPageCountToShow}
	<div>
		<InputGroup class="input-group-sm">
			{#if minPageCountForFirstLast !== null && max >= minPageCountForFirstLast}
				<Button
					on:click={() => {
						page = 1;
					}}
					disabled={page <= 1}
				>
					&lt;&lt;
				</Button>
			{/if}
			<Button
				on:click={() => {
					page -= 1;
				}}
				disabled={page <= 1}
			>
				&lt;
			</Button>
			<input
				type="number"
				class="form-control"
				min={1}
				{max}
				bind:value={inputValue}
				on:change={() => {
					page = inputValue;
				}}
				style:width={`${width}ch`}
			/>
			<span class="input-group-text" style:width={`${width}ch`}>/{max}</span>
			<Button
				on:click={() => {
					page += 1;
				}}
				disabled={page >= max}
			>
				&gt;
			</Button>
			{#if minPageCountForFirstLast !== null && max >= minPageCountForFirstLast}
				<Button
					on:click={() => {
						page = max;
					}}
					disabled={page >= max}
				>
					&gt;&gt;
				</Button>
			{/if}
		</InputGroup>
	</div>
{/if}

<style>
	input[type='number']::-webkit-outer-spin-button,
	input[type='number']::-webkit-inner-spin-button {
		-webkit-appearance: none;
		margin: 0;
	}

	input[type='number'] {
		-moz-appearance: textfield;
		appearance: textfield;
		text-align: center;
	}
</style>
