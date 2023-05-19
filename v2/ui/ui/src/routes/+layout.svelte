<script lang="ts">
	import '$lib/bootstrap.scss';
	import { Col, Container, Row } from 'sveltestrap';
	import Navbar from '$lib/components/Navbar.svelte';
	import CookieConsent from '$lib/components/CookieConsent.svelte';
	import ImageModal from '$lib/components/ImageModal.svelte';
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
<ImageModal />

<style>
	/* :global(*){
		outline: dotted 1px aquamarine !important;
	} */
	:global(.cursor-pointer) {
		cursor: pointer;
	}
</style>
