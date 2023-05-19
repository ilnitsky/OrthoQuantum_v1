<script lang="ts">
	import { Alert, Card, CardBody, Collapse } from 'sveltestrap';
	import Paginator, { getPage } from '$lib/components/Paginator.svelte';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';
	import type { MultiOrthoID } from '$lib/dbTypes';
	import { immerDeriveMap } from '$lib/immerUtil';
	import { getStore } from './store';
	import { dev } from '$app/environment';

	let multi_ortho = immerDeriveMap(
		getStore(),
		(store) => store.output.multi_ortho,
		(v) => v ?? []
	);

	export let selection: Set<MultiOrthoID>;

	function toggle(n: MultiOrthoID) {
		selection.has(n) ? selection.delete(n) : selection.add(n);
		selection = selection;
	}

	// TODO: bold new entries?
	let pageSize = dev ? 1 : 40;
	let page = 1;
	$: idxPageOffset = 1 + (page - 1) * pageSize;
</script>

<Collapse id="multi_ortho_table_container" isOpen={$multi_ortho.length !== 0}>
	<Card>
		<CardBody class="table-responsive">
			<Alert class="alert-info">
				Some query strings yielded multiple matching orthogroups. You can choose the ones you are
				interested in and re-submit.
			</Alert>
			<div class="container">
				<div class="scrollable">
					<table class="table table-bordered table-responsive table-sm">
						<thead>
							<tr>
								<th scope="col" />
								<th scope="col">Query</th>
								<th scope="col">OrthoDB ID</th>
								<th scope="col">Gene Name</th>
								<th scope="col">Description</th>
								<th scope="col">Gene Count</th>
								<th scope="col">Present in #&nbsp;species</th>
							</tr>
						</thead>
						<tbody>
							{#each getPage($multi_ortho, page, pageSize) as row, idx}
								<tr class:table-active={selection.has(row[0])}>
									<th
										tabindex="-1"
										scope="row"
										role="button"
										on:click|self={() => {
											toggle(row[0]);
										}}
									>
										<label class="form-check-label" for={`check_${row[0]}`}
											>{idxPageOffset + idx}</label
										>
										<input
											id={`check_${row[0]}`}
											type="checkbox"
											class="form-check-input"
											checked={selection.has(row[0])}
											on:click={() => {
												toggle(row[0]);
											}}
										/>
									</th>
									<td>{row[1]}</td>
									<td>
										<a
											href="https://data.orthodb.org/v11/fasta?id={row[2]}"
											target="_blank"
											rel="noopener noreferrer"
											>{row[2]}
										</a>
									</td>
									<td>{row[3]}</td>
									<td>{row[4]}</td>
									<td>{row[5]}</td>
									<td>{row[6]}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
			<div class="d-flex w-100 justify-content-center">
				<Paginator bind:page {pageSize} itemCount={$multi_ortho.length} minPageCountToShow={1} />
			</div>

			<Tooltip target="multi_ortho_table_container" placement="top">
				Choose orthogroups to investigate further
			</Tooltip>
		</CardBody>
	</Card>
</Collapse>

<style>
	.container {
		overflow-x: scroll;
		width: 100%;
	}
	.scrollable {
		width: fit-content;
	}
	tbody > tr > th {
		text-align: center;
	}
	tbody > tr > th * {
		cursor: pointer;
	}
</style>
