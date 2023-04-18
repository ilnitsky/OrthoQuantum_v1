<script lang="ts">
	import Select from 'svelte-select';
	import type { Species, Taxon } from '$lib/dbTypes';
	import { keyToStore } from '$lib/valtioUtil';
	import { getStore } from './store';

	export let taxon: Taxon | undefined;
	let selectedSpecies: Species['species'][number] | undefined;
	let speciesCache = new Map<Taxon['id'], Species['species']>();
	export let initSpecies: Species | undefined;
	if (initSpecies) {
		speciesCache.set(initSpecies.taxon_id, initSpecies.species);
	}

	// init bg fetch for all species to fill speciesCache
	// TODO: put in localstoreage?
	fetch('/api/getSpecies')
		.then((r) => {
			if (!r.ok) {
				throw new Error(`Request not ok: ${r.status} ${r.statusText}`);
			}
			return r.json();
		})
		.then((json) => {
			if (!json.ok) {
				throw new Error(`JSON not ok: ${json}`);
			}
			const res = json.data as Species[];
			for (const sp of res) {
				speciesCache.set(sp.taxon_id, sp.species);
			}
		})
		.catch((err) => {
			console.error('Failed to get all spicies:', err);
		});

	let speciesColl: Species['species'] | undefined;

	function updateSpecies(new_taxon?: Taxon) {
		if (!new_taxon) {
			speciesColl = undefined;
			return;
		}
		const cached = speciesCache.get(new_taxon.id);
		if (cached) {
			speciesColl = cached;
			return;
		}
		// no species array cached - get it from api
		speciesColl = undefined;
		fetch('/api/getSpecies?' + new URLSearchParams([['taxon_id', new_taxon.id]]))
			.then((r) => {
				if (!r.ok) {
					throw new Error(`Request not ok: ${r.status} ${r.statusText}`);
				}
				return r.json();
			})
			.then((json) => {
				if (!json.ok) {
					throw new Error(`JSON not ok: ${json}`);
				}
				const res = json.data as Species;
				speciesCache.set(res.taxon_id, res.species);
				if (new_taxon.id === taxon?.id) {
					speciesColl = res.species;
				}
			})
			.catch((err) => {
				console.error('Species get failed:', err);
			});
	}

	function onSpeceiesCollUpdate() {
		// update selectedSpecies when new collection is loaded
		if (!speciesColl || !selectedSpecies) {
			return;
		}
		const tgt = selectedSpecies?.taxid;
		selectedSpecies = speciesColl.find((sp) => sp.taxid == tgt);
	}

	$: updateSpecies(taxon);
	$: speciesColl, onSpeceiesCollUpdate();
	$: currentSpeciesColl = speciesColl;

	const store = getStore();
	keyToStore(store.input, 'species').subscribe((v) => {
		if (!v) {
			selectedSpecies = undefined;
			return;
		}
		const sel = speciesColl?.find((it) => it.taxid == v);
		if (sel) {
			selectedSpecies = sel;
			return;
		}
		selectedSpecies = {
			taxid: v,
			name: 'Loading...'
		};
	});

	let filterText = '';
	// if filterText is a number - generate a matching entry
	function handleFilter() {
		if (!currentSpeciesColl || !speciesColl) {
			return;
		}
		const num = parseInt(filterText);

		if (currentSpeciesColl === speciesColl) {
			// items was not modified
			if (Number.isInteger(num)) {
				// adding extra value to represent the entered number
				currentSpeciesColl = [...speciesColl, { taxid: num, name: filterText }];
			}
		} else {
			// items were modified
			if (Number.isInteger(num)) {
				// filterText is an integer, updating the last value
				const last = currentSpeciesColl.length - 1;
				if (currentSpeciesColl[last].name == filterText) {
					return;
				}
				currentSpeciesColl[last].taxid = num;
				currentSpeciesColl[last].name = filterText;
				currentSpeciesColl = currentSpeciesColl;
			} else {
				// filterText is not an integer, removing extra value
				currentSpeciesColl = speciesColl;
			}
		}
	}
</script>

<Select
	class="mt-2 form-control my-select-style"
	on:filter={handleFilter}
	bind:value={selectedSpecies}
	bind:filterText
	items={currentSpeciesColl}
	itemId="taxid"
	label="name"
	disabled={!taxon || !currentSpeciesColl}
	loading={taxon && !currentSpeciesColl}
	placeholder="Select species/enter taxid"
	--border-hover="1px solid #ced4da"
	--border-focused="1px solid #f4aa90"
	--border-radius="0.375rem"
	--item-hover-bg="#fcf2ed"
	--item-is-active-bg="#fcd1bb"
	--item-is-active-color="#333"
/>
