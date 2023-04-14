import { getContext, setContext } from "svelte";
import type { Store, Query, InitData, Data } from '$lib/dbTypes';
import { initStore } from "$lib/sseStore";

export const storeKey = Symbol();

export function getStore() {
  return getContext(storeKey) as Store<Query>;
}

export function setStore<T extends Data>(data: InitData<T>, url: URL, isNew: boolean){
  const store = initStore(data, url, isNew);
	setContext(storeKey, store);
  return store;
}