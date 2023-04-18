import { getContext } from 'svelte';
import type { Store, Query } from '$lib/dbTypes';

export const storeKey = Symbol();

export function getStore() {
	return getContext(storeKey) as Store<Query>;
}
