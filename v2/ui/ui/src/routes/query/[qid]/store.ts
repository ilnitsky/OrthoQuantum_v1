import { getContext } from 'svelte';
import type { Query } from '$lib/dbTypes';
import type { ImmerStore } from '$lib/immerUtil';

export const storeKey = Symbol();

export function getStore(): ImmerStore<Query> {
	return getContext(storeKey);
}
