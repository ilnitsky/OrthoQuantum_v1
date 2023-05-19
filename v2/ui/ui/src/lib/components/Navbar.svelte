<script lang="ts">
	import { Collapse, NavbarBrand, NavbarToggler } from 'sveltestrap';

	import NavbarContents from './NavbarContents.svelte';
	import { dev } from '$app/environment';

	let isOpen = false;
	let innerWidth: number;
	$: isCollapsed = innerWidth <= 576;
	$: if (!isCollapsed) {
		isOpen = false;
	}
</script>

<svelte:window bind:innerWidth />

<nav class="navbar navbar-expand-sm navbar-light bg-light sticky-top">
	<div class="container-fluid col-lg-8 col-md-10 col-12">
		<NavbarBrand href="/">OrthoQuantum</NavbarBrand>
		{#if dev}
			<span class="d-none d-xl-block">size: xl</span>
			<span class="d-none d-lg-block d-xl-none">size: lg</span>
			<span class="d-none d-none d-md-block d-lg-none">size: md</span>
			<span class="d-none d-sm-block d-md-none">size: sm</span>
			<span class="d-block d-sm-none">size: x-small (default)</span>
		{/if}

		<NavbarToggler on:click={() => (isOpen = !isOpen)} />
		<!-- Hack to prevent invalid animation on load (thanks sveltestrap) -->
		<div class="d-none d-sm-block">
			<Collapse isOpen navbar>
				<NavbarContents />
			</Collapse>
		</div>
		<div class="d-sm-none" style:display="contents">
			<Collapse {isOpen} navbar>
				<NavbarContents />
			</Collapse>
		</div>
	</div>
</nav>

<style>
	/* limit navbar size on xxl */
	@media (min-width: 1400px) {
		.container-fluid {
			max-width: 1140px;
		}
	}
</style>
