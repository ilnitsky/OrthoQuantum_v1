<script lang="ts">
	import { Button, Modal, ModalBody } from 'sveltestrap';

	export let open = false;
	export let src: string | undefined;
	export let lazy = false;

	function toggle() {
		open = !open;
	}
	function closeKeypress(e: KeyboardEvent) {
		switch (e.key) {
			case ' ':
			case 'Enter':
			case 'Escape':
				open = false;
				e.preventDefault();
				break;
		}
	}
</script>

<Modal isOpen={open && src !== undefined} {toggle} class="my-large-modal m-lg-5 m-0 mt-lg-0">
	<div slot="external" class="text-end close-bar" on:click={toggle} on:keydown={closeKeypress}>
		<Button color="link" class="text-white my-close-btn p-2">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="currentColor"
				class="bi bi-x-lg"
				viewBox="0 0 16 16"
				width="100%"
				height="100%"
			>
				<path
					d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854Z"
				/>
			</svg>
		</Button>
	</div>
	<ModalBody class="d-flex justify-content-center">
		<img
			{src}
			class="max-width-image"
			alt="Interface screenshot"
			loading={lazy ? 'lazy' : 'eager'}
			decoding={lazy ? 'async' : 'auto'}
		/>
	</ModalBody>
</Modal>

<style>
	.close-bar {
		/* Height of the navbar */
		height: 3.5rem;
	}
	:global(.my-close-btn) {
		/* Height of the navbar */
		height: 3.5rem;
		width: 3.5rem;
	}
	.max-width-image {
		max-width: 100%;
		height: auto;
	}
	:global(.my-large-modal) {
		max-width: initial;
	}
</style>
