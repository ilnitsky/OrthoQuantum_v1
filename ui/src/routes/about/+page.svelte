<script lang="ts">
	import ImageModal from '$lib/components/ImageModal.svelte';
	import { onMount } from 'svelte';
	import PageContent from './PageContent.svelte';
	import { addAlert, updateAlert } from '$lib/components/Alerts.svelte';

	let open = false;
	let src: string | undefined;

	function imageSelected(e: CustomEvent<string>) {
		src = e.detail;
		open = true;
	}

	onMount(() => {
		let id = 0;
		setTimeout(() => {
			id = addAlert('hello', undefined, undefined, true);
		}, 1000);
		setTimeout(() => {

			updateAlert(id, (a)=>{
				console.log("updated")
				a.text = "New data"
			});
		}, 2000);
		setTimeout(() => {
			const t = updateAlert(id, (a)=>{
				console.log("updated")
				a.text = "New data2"
			});
			console.log("updated?", t);
		}, 5000);
		setTimeout(() => {
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
			addAlert('hellohellohello hellovhellohello hellohellohello', 'Title', 'danger');
		}, 2000);
	});
</script>

<PageContent on:imageSelected={imageSelected} />
<ImageModal {src} {open} />
