<script lang="ts">
	import { Alert, Card, CardBody, Collapse } from 'sveltestrap';
	import Paginator, { getPage } from '$lib/components/Paginator.svelte';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';

	let table = [
		{
			selected: true,
			query: 'SMPDL3A1',
			orthodb_id: '1574805at7742',
			gene_name: 'SMPDL3A',
			description: 'sphingomyelin phosphodiesterase acid like 3A',
			gene_count: '474',
			species_count: '462'
		},
		{
			selected: false,
			query: 'SMPDL3A2',
			orthodb_id: '1574805at7742',
			gene_name: 'SMPDL3A',
			description: 'sphingomyelin phosphodiesterase acid like 3A',
			gene_count: '474',
			species_count: '462'
		}
	];

	// TODO: bold new entries?
	let pageSize = 1; // TODO: 40
	let page = 1;
</script>

<Collapse id="multi_ortho_table_container" isOpen={table && table.length !== 0}>
	<Card>
		<CardBody class="table-responsive">
			<Alert class="alert-info">
				Some query strings yielded multiple matching orthogroups. Select the ones you are interested
				in and re-submit.
			</Alert>

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
					{#each getPage(table, page, pageSize) as row}
						<tr class:table-active={row.selected}>
							<th
								scope="row"
								role="button"
								tabindex="0"
								on:click={() => {
									row.selected = !row.selected;
								}}
							>
								<input type="checkbox" class="form-check-input" bind:checked={row.selected} />
							</th>
							<td>{row.query}</td>
							<td>
								<a
									href="https://data.orthodb.org/v11/fasta?id={row.orthodb_id}"
									target="_blank"
									rel="noopener noreferrer"
									>{row.orthodb_id}
								</a>
							</td>
							<td>{row.gene_name}</td>
							<td>{row.description}</td>
							<td>{row.gene_count}</td>
							<td>{row.species_count}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<div class="d-flex w-100 justify-content-center">
				<Paginator bind:page {pageSize} itemCount={table.length} minPageCountToShow={1} />
			</div>

			<Tooltip target="multi_ortho_table_container" placement="top">
				Choose orthogroups to investigate further
			</Tooltip>
		</CardBody>
	</Card>
</Collapse>
