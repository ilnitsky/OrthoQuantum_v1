<script lang="ts">
	import { keyToStore } from '$lib/sseStore';
	import Select from 'svelte-select';
	import { getStore } from './store';

	let tax_id = [
		{ value: 1, label: 'one111' },
		{ value: 2, label: 'two' },
		{ value: 3, label: 'three' }
	];
	let filterText = '';
	let items = tax_id;

	// if filterText is a number - generate a matching entry
	function handleFilter() {
		const num = parseInt(filterText);

		if (items === tax_id) {
			// items was not modified
			if (Number.isInteger(num)) {
				// adding extra value to represent the entered number
				items = [...tax_id, { value: num, label: filterText }];
			}
		} else {
			// items were modified
			if (Number.isInteger(num)) {
				// filterText is an integer, updating the last value
				const last = items.length - 1;
				if (items[last].label == filterText){
					return;
				}
				items[last].value = num;
				items[last].label = filterText;
				items = items;
			} else {
				// filterText is not an integer, removing extra value
				items = tax_id;
			}
		}
	}
	const store = getStore()
	let species: (typeof tax_id[number])|undefined;
	keyToStore(store.input, 'species').subscribe((v)=>{
		species = tax_id.find((it)=>it.value == v)
	});
</script>

<!-- id="taxid-input" -->
<Select
	class="mt-2 form-control my-select-style"
	on:filter={handleFilter}
	bind:value={species}
	bind:filterText
	{items}
	placeholder="Select species/enter taxid"
	--border-hover="1px solid #ced4da"
	--border-focused="1px solid #f4aa90"
	--border-radius="0.375rem"
	--item-hover-bg="#fcf2ed"
	--item-is-active-bg="#fcd1bb"
	--item-is-active-color="#333"
/>
