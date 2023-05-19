<script lang="ts" context="module">
	import { writable } from 'svelte/store';
	export const COOKIE_NAME = 'COOKIE_CONSENT';
	export const COOKIE_VALUE = 'true';

	export const cookieConsent = writable(true);
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import { Button, Offcanvas, Container, Row, Col } from 'sveltestrap';

	function give_consent() {
		document.cookie = `${COOKIE_NAME}=${COOKIE_VALUE};max-age=31536000;path=/;samesite=lax`;
		$cookieConsent = true;
	}

	// Can't be open before mount: issues with backdrop
	onMount(() => {
		$cookieConsent = document.cookie
			.split(';')
			.some((item) => item.trim().startsWith(`${COOKIE_NAME}=${COOKIE_VALUE}`));
	});
</script>

<Offcanvas isOpen={!$cookieConsent} placement="bottom" backdrop style="height: auto;">
	<Container fluid>
		<Row class="justify-content-center">
			<Col xl="6" md="8" sm="10">
				<h3>Cookie consent</h3>
				<p>
					This website uses cookies to accomplish essential functionality. No user tracking across
					other websites for advertizing or other purposes is performed.
				</p>
				<Button color="success" on:click={give_consent}>I accept cookies</Button>
				<Button color="danger" class="float-end" href="https://en.wikipedia.org/wiki/HTTP_cookie">
					Leave
				</Button>
			</Col>
		</Row>
	</Container>
</Offcanvas>

<style>
	h3 {
		color: var(--bs-pink);
		white-space: nowrap;
	}
</style>
