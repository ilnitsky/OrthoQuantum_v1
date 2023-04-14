<script lang="ts">
	import { onMount } from 'svelte';
	import { Button, Offcanvas, Container, Row, Col } from 'sveltestrap';

	let cookie_consent = true;

	function give_consent() {
		document.cookie = 'COOKIE_CONSENT=true;max-age=31536000;path=/;samesite=lax';
		cookie_consent = true;
	}

	// Can't be open before mount: issues with backdrop
	onMount(() => {
		cookie_consent = document.cookie
			.split(';')
			.some((item) => item.trim().startsWith('COOKIE_CONSENT=true'));
	});
</script>

<Offcanvas isOpen={!cookie_consent} placement="bottom" backdrop style="height: auto;">
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
