<script lang="ts">
	// interacting with phyd3 through the globals on window... Sad, but manageable
	/* eslint-disable @typescript-eslint/no-explicit-any */

	import { onMount, tick } from 'svelte';
	import { Button, Input, Nav, NavItem, NavLink } from 'sveltestrap';
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import { browser } from '$app/environment';

	export let url: string;
	export let taskid: string;
	export let leafCount: number;

	let phyd3_ref: HTMLDivElement | undefined;
	let svg_ref: HTMLDivElement | undefined;

	// Rerender phyd3 if viewport becomes larger than the original rendered width

	let elementWidth = 0;
	let renderedWidth = 0;
	let resizeTimer: ReturnType<typeof setTimeout> | undefined;

	const height = 2000;

	let isInteractive = true;

	let showGroups = false;
	let showSpecies = true;
	let dynamicHide = false;

	let phyd3_rendered = false;
	let svg_rendered = false;

	let rawZoom = 100;

	let libLoaded: () => void;
	function checkLibLoaded() {
		if ((window as any).renderPhyd3) {
			libLoaded();
		} else {
			setTimeout(checkLibLoaded, 100);
		}
	}
	let interactionQueue = new Promise<void>((resolve) => {
		libLoaded = resolve;
	});

	onMount(checkLibLoaded);

	function transformZoom(val: number): number {
		if (val > 100) {
			val = val * 2 - 100;
		}
		return val / 100;
	}
	$: zoom = transformZoom(rawZoom);

	function updateNodeVisibility(doShowGroups: boolean, doShowSpecies: boolean) {
		if (!browser) {
			return;
		}
		if (!isInteractive) {
			switchToInteractive();
		}
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.updateNodeVisibility(doShowGroups, doShowSpecies);
		});
	}

	function updateDynamicHide(newDynamicHide: boolean) {
		if (!browser) {
			return;
		}
		if (!isInteractive) {
			switchToInteractive();
		}
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.dynamicHide(newDynamicHide);
		});
	}

	async function redraw_phyd3(url: string, taskid: string, leafCount: number) {
		if (!browser) {
			return;
		}
		const scaleX = 0.4;
		const scaleY = 0.01183 * leafCount;
		let showNodesType: string;
		if (showGroups && showSpecies) {
			showNodesType = 'all';
		} else if (showGroups) {
			showNodesType = 'only inner';
		} else {
			showNodesType = 'only leaf';
		}
		const showNodeNames = showGroups || showSpecies;
		const opts = {
			// editable
			origScaleX: scaleX,
			scaleX,
			origScaleY: scaleY,
			scaleY,
			height,
			showNodesType,
			showNodeNames,
			dynamicHide,
			taskid_for_links: taskid,
			// defaults
			invertColors: false,
			lineupNodes: true,
			showDomains: false,
			showDomainNames: false,
			showDomainColors: true,
			showGraphs: true,
			showGraphLegend: true,
			showLength: false,
			nodeHeight: 10,
			scaleStep: 0.23,
			margin: 100,
			showPhylogram: true,
			showTaxonomy: false,
			showFullTaxonomy: false,
			showSequences: false,
			showLabels: false,
			showTaxonomyColors: false,
			backgroundColor: '#f5f5f5',
			foregroundColor: '#000000',
			nanColor: '#f5f5f5',
		};
		interactionQueue = interactionQueue
			.then(() => {
				isInteractive = true;
				phyd3_rendered = false;
				return tick();
			})
			.then(() => (window as any).renderPhyd3(url, phyd3_ref, opts))
			.then(() => {
				phyd3_rendered = true;
				renderedWidth = elementWidth;
			});
	}

	// bindings to phyd3
	function resetZoom() {
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.resetZoom();
		});
	}
	function resetPos() {
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.resetPos();
		});
	}
	function fitTree() {
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.fitTree();
		});
	}
	function renderSVG() {
		if (!isInteractive && svg_rendered) {
			return;
		}
		interactionQueue = interactionQueue
			.then(() => {
				isInteractive = false;
				svg_rendered = false;
				return tick();
			})
			.then(() => {
				if (svg_ref) {
					svg_ref.innerHTML = (window as any).phyd3.phylogram.getSVGData();
				}
				svg_rendered = true;
			});
	}
	function renderPNG() {
		interactionQueue = interactionQueue.then(() => {
			(window as any).phyd3.phylogram.renderPNG();
		});
	}
	function onWidthChange() {
		if (!(browser && isInteractive && phyd3_rendered)) {
			return;
		}
		clearTimer();
		resizeTimer = setTimeout(() => {
			interactionQueue = interactionQueue.then(() => {
				if (isInteractive && phyd3_rendered && renderedWidth < elementWidth) {
					redraw_phyd3(url, taskid, leafCount);
				}
			});
		}, 1500);
	}

	function clearTimer() {
		clearTimeout(resizeTimer);
		resizeTimer = undefined;
	}

	function switchToInteractive() {
		interactionQueue = interactionQueue.then(() => {
			isInteractive = true;
			if (renderedWidth < elementWidth) {
				redraw_phyd3(url, taskid, leafCount);
			} else {
				phyd3_rendered = true;
			}
		});
	}
	$: if (svg_ref && isInteractive) {
		svg_ref.innerHTML = '';
	}

	$: redraw_phyd3(url, taskid, leafCount);
	$: updateNodeVisibility(showGroups, showSpecies);
	$: updateDynamicHide(dynamicHide);

	$: elementWidth, onWidthChange();
	$: if (!(isInteractive && phyd3_rendered)) {
		clearTimer();
	}
</script>

<!-- <svelte:head>
	<link rel="stylesheet" href="/static/phyd3.bundle.css" />
	<script src="/static/phyd3.bundle.js"></script>
</svelte:head> -->

<h3 id="tree_title" class="mt-3 text-center">Phylogenetic profile plot</h3>
<!-- tree_progress_bar -->
<ProgressBar />
<div class="my-2">
	<p>
		The columns show the orthogroups, with the same name as the query proteins. Rows of the heatmap
		show the eukaryotic genomes, major taxa on the species tree are labeled with different colors.
	</p>
	<p>
		To scale the graph use a mouse wheel while holding Alt to scale x axis and/or Ctrl to scale y
		axis.
	</p>
	<p>Legend:</p>
	<ul>
		<li>
			<span style:background-color="#170a1c" class="tree-legend" />
			<span>No findings</span>
		</li>
		<li>
			<span style:background-color="#666666" class="tree-legend" />
			<span>Scheduled to be BLAST'ed</span>
		</li>
		<li>
			<span style:background-color="#f72585" class="tree-legend" />
			<span>Found via BLAST</span>
		</li>
		<li>
			<span style:background-color="#228cdb" class="tree-legend" />
			<span>Found in OrthoDB</span>
		</li>
	</ul>
</div>

<Nav tabs>
	<NavItem>
		<NavLink active={isInteractive} on:click={switchToInteractive}>Interactive graph</NavLink>
	</NavItem>
	<NavItem>
		<button
			class="nav-link"
			class:active={!isInteractive}
			class:disabled={isInteractive && !phyd3_rendered}
			on:click|preventDefault={renderSVG}
		>
			Static image
		</button>
	</NavItem>
	<NavItem class="ms-auto">
		<NavLink disabled={!(isInteractive && phyd3_rendered)} on:click={renderPNG}>
			Download image
		</NavLink>
	</NavItem>
	<NavItem>
		<NavLink target="_blank" rel="noopener noreferrer" href="#">Download csv</NavLink>
	</NavItem>
</Nav>

<div class="mt-2 d-flex align-items-start my-toolbar" class:flex-column={!isInteractive}>
	{#if isInteractive}
		<div class="d-inline-block">
			<Input type="checkbox" label="Show group names" bind:checked={showGroups} />
			<Input type="checkbox" label="Show species names" bind:checked={showSpecies} />
		</div>
		<Input type="checkbox" label="Dynamic hide" class="ms-3" bind:checked={dynamicHide} />
		<Button class="ms-3 btn btn-sm" on:click={resetZoom}>Reset Zoom</Button>
		<Button class="ms-1 btn btn-sm" on:click={resetPos}>Reset Position</Button>
		<Button class="ms-1 btn btn-sm" on:click={fitTree}>Fit Tree To View</Button>
	{:else}
		<Input type="range" min="1" max="200" step="1" bind:value={rawZoom} />
		<span class="align-self-center">{zoom.toFixed(2)}x</span>
	{/if}
</div>
<div style:height={`${height}px`} bind:clientWidth={elementWidth} class="data_container">
	<!-- Rendering stub -->
	<div class="rendering" class:d-none={isInteractive ? phyd3_rendered : svg_rendered}>
		Rendering...
	</div>
	<!-- phyd3 -->
	<div
		bind:this={phyd3_ref}
		style:visibility={isInteractive && phyd3_rendered ? 'initial' : 'hidden'}
		class:d-none={!isInteractive && svg_rendered}
	/>
	<!-- svg -->
	<div class:d-none={isInteractive || !svg_rendered} class="overflow-scroll">
		<div bind:this={svg_ref} id="phyd3svg" style:transform={`scale(${zoom})`} />
	</div>
</div>

<style>
	.rendering {
		background-color: var(--bs-body-bg);
		text-align: center;
		z-index: 10;
	}
	.my-toolbar {
		min-height: 3.5rem;
	}
	.data_container {
		overflow: hidden;
		position: relative;
	}
	.data_container > * {
		position: absolute;
		left: 0;
		top: 0;
		width: 100%;
		height: 100%;
	}
	.nav-link.disabled {
		transition: none;
	}
	span.tree-legend {
		width: 1.25rem;
		height: 1.25rem;
		border: 1px solid black;
		display: inline-block;
		margin-right: 0.25rem;
		vertical-align: text-bottom;
	}
	#phyd3svg {
		position: absolute;
		top: 0;
		left: 0;
		transform-origin: 0 0;
	}
	h3 {
		color: var(--bs-pink);
		white-space: nowrap;
	}
	:global(.phyd3-popup) {
		position: fixed;
		display: none;
		background-color: #ffd299;
		border-radius: 10px;
		padding: 6px 15px;
		box-shadow: 2px 2px 5px #aaa;
		border: solid #777 1px;
		width: 300px;
	}
</style>
