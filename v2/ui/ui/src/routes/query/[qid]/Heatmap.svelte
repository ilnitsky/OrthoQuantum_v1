<script lang="ts">
	import {
		Button,
		Card,
		CardBody,
		Col,
		Collapse,
		Input,
		InputGroup,
		InputGroupText,
		Row,
	} from 'sveltestrap';
	import ConstrainedNum from '$lib/components/ConstrainedNum.svelte';
	import Paginator, { getPage } from '$lib/components/Paginator.svelte';
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';
	import image from './Correlation_preview.png';
	import { modal } from '$lib/components/ImageModal.svelte';
	import { dev } from '$app/environment';

	// TODO: tmp
	let isProgress = true;
	let isData = true;
	let optionsOpen = false;

	let quantileMin = 0;
	let quantileMax = 1;
	let correlationMin = -1;
	let correlationMax = 1;

	let table = [1, 2, 3, 4];
	let page = 1;
	let pageSize = dev ? 1 : 20;

	function reset() {
		quantileMin = 0;
		quantileMax = 1;
		correlationMin = -1;
		correlationMax = 1;
		pageSize = 20;
	}
</script>

{#if isProgress || isData}
	<h3 id="corr_matrix_title" class="text-center">Correlation matrix</h3>
	<Tooltip target="corr_matrix_title" placement="bottom">
		The colors on the correlation matrix reflect the values of the Pearson correlation coefficient,
		on both axes a color bar is added corresponding to the percentage of homologs presence in
		species: a high percentage corresponds to black, a low one is colored bright red. The table
		contains sorted pairwise correlations.
	</Tooltip>
	<ProgressBar />
{/if}

{#if isData}
	<Row id="heatmap_container" class="mx-0">
		<Col lg="6" class="text-center px-0 pe-lg-2 mb-3 ">
			<img
				id="heatmap_img"
				style:max-width="1100px"
				class="mx-auto w-100 cursor-pointer"
				alt="heatmap"
				src={image}
				use:modal={image}
			/>
		</Col>
		<Col lg="6" class="px-0 ps-lg-2">
			<div class="d-flex flex-row justify-content-between mb-2">
				<!-- invisible button mirroring the options button for alignment -->
				<Button class="invisible" size="sm">Options</Button>
				<Paginator bind:page {pageSize} itemCount={table.length} />
				<Button
					id="corr_table_options_show"
					class="float-end"
					size="sm"
					active={optionsOpen}
					on:click={() => {
						optionsOpen = !optionsOpen;
					}}
				>
					Options
				</Button>
			</div>
			<Collapse id="corr_table_options_collapse" isOpen={optionsOpen}>
				<Card class="mb-2">
					<CardBody class="p-2">
						<Row>
							<div class="d-flex flex-row justify-content-start flex-wrap">
								<div class="m-1">
									<InputGroup size="sm">
										<ConstrainedNum
											min={0}
											max={1}
											bind:value={quantileMin}
											style="width: 7ch;"
											class="form-control "
										/>
										<InputGroupText>≤&nbsp;quantile&nbsp;≤</InputGroupText>
										<ConstrainedNum
											min={0}
											max={1}
											bind:value={quantileMax}
											style="width: 7ch;"
											class="form-control"
										/>
									</InputGroup>
								</div>
								<div class="m-1">
									<InputGroup size="sm">
										<ConstrainedNum
											min={-1}
											max={1}
											bind:value={correlationMin}
											style="width: 7ch;"
											class="form-control"
										/>
										<InputGroupText>≤&nbsp;correlation&nbsp;≤</InputGroupText>
										<ConstrainedNum
											min={-1}
											max={1}
											bind:value={correlationMax}
											style="width: 7ch;"
											class="form-control"
										/>
									</InputGroup>
								</div>
								<div class="m-1">
									<InputGroup style="width: 11em;" class="mb-2" size="sm">
										<InputGroupText>Page size</InputGroupText>
										<Input type="number" bind:value={pageSize} min={1} id="page_size" />
									</InputGroup>
								</div>
								<div style:min-width="2rem" />
								<div class="m-1 ms-auto">
									<Button
										id="reset_corr_settings"
										color="danger"
										outline
										class="float-end"
										size="sm"
										on:click={reset}
									>
										Reset
									</Button>
								</div>
							</div>
						</Row>
					</CardBody>
				</Card>
			</Collapse>
			<Row class="">
				<Col>
					<div class="table-responsive">
						<table class="table table-bordered table-responsive table-sm">
							<thead>
								<tr>
									<th scope="col">Prot A</th>
									<th scope="col">Prot B</th>
									<th scope="col">Corr</th>
									<th scope="col">Quantile</th>
								</tr>
							</thead>
							<tbody>
								{#each getPage(table, page, pageSize) as row}
									<tr>
										<td>{row}</td>
										<td>{row}</td>
										<td>{row}</td>
										<td>{row}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</Col>
			</Row>
		</Col>
	</Row>
{/if}

<style>
	h3 {
		color: var(--bs-pink);
		white-space: nowrap;
	}
</style>
