<script lang="ts">
	import '$lib/bootstrap.scss';
	import { Alert, Col, Container, Row } from 'sveltestrap';
	import Navbar from '$lib/components/Navbar.svelte';
	import CookieConsent from '$lib/components/CookieConsent.svelte';
</script>

<Navbar />
<Container fluid>
	<Row class="justify-content-center">
		<Col md="10" lg="8">
			<slot />
		</Col>
	</Row>
</Container>
<CookieConsent />

<style>
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
