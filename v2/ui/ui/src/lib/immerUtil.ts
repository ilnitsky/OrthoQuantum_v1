import {
	freeze,
	nothing,
	produce as immerProduce,
	type Immutable,
	castImmutable,
	applyPatches as immerApplyPatches,
	enablePatches,
	type Patch,
} from 'immer';
import { onDestroy } from 'svelte';
export type { Immutable, Patch } from 'immer';
import type { Readable, Unsubscriber } from 'svelte/store';

export function immerStore<T extends Parameters<typeof immerApplyPatches>[0]>(
	initValue: T,
	deepFreeze = false
): ImmerStore<T> {
	enablePatches();
	let value = castImmutable(freeze(initValue, deepFreeze));

	const subscribers = new Set<(val: Immutable<T>) => void>();
	function set(new_value: T) {
		if (value === new_value) {
			return;
		}
		value = castImmutable(freeze(new_value, deepFreeze));
		for (const subscriber of subscribers) {
			subscriber(value);
		}
	}
	function applyPatches(patches: Patch[]) {
		value = immerApplyPatches(value, patches);
		for (const subscriber of subscribers) {
			subscriber(value);
		}
	}

	function get(): Immutable<T> {
		return value;
	}
	function produce(
		recipe: (draft: T) => T | void | undefined | T extends undefined ? typeof nothing : never
	) {
		const new_value = immerProduce(value, recipe);
		if (value === new_value) {
			return;
		}
		value = new_value;
		for (const subscriber of subscribers) {
			subscriber(value);
		}
	}
	function subscribe(subscriber: (val: Immutable<T>) => void) {
		subscribers.add(subscriber);
		subscriber(value);
		return () => {
			subscribers.delete(subscriber);
		};
	}
	return { set, get, applyPatches, produce, subscribe };
}

export interface ImmerStore<T> extends Readable<Immutable<T>> {
	set(new_value: T): void;
	get(): Immutable<T>;
	applyPatches(patches: Patch[]): void;
	produce(
		recipe: (draft: T) => T | void | undefined | (T extends undefined ? typeof nothing : never)
	): void;
}
function identity<T>(v: T): T {
	return v;
}
export function immerDerive<StoreT, SubStoreT>(
	store: ImmerStore<StoreT>,
	accessor: (value: Immutable<StoreT>) => Immutable<SubStoreT>
): Readable<Immutable<SubStoreT>> {
	return immerDeriveMap(store, accessor, identity);
}

export function immerDeriveMap<StoreT, SubStoreT, T>(
	store: ImmerStore<StoreT>,
	accessor: (value: Immutable<StoreT>) => Immutable<SubStoreT>,
	map: (value: Immutable<SubStoreT>) => T
): Readable<T> {
	const subscribers = new Set<(val: T) => void>();
	let unsub: Unsubscriber | null;
	// if unsub is null - value is garbage
	let immerValue: Immutable<SubStoreT>;
	let value: T;

	function subscribe(subscriber: (val: T) => void) {
		subscribers.add(subscriber);
		if (unsub) {
			subscriber(value);
		} else {
			unsub = store.subscribe((v) => {
				const new_value = accessor(v);
				if (unsub && immerValue === new_value) {
					return;
				}
				immerValue = new_value;
				value = map(immerValue);
				for (const subscriber of subscribers) {
					subscriber(value);
				}
			});
		}
		return () => {
			subscribers.delete(subscriber);
			if (subscribers.size === 0) {
				// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
				unsub!();
				unsub = null;
			}
		};
	}
	return { subscribe };
}

export function immerSubKey<StoreT, SubStoreT>(
	store: ImmerStore<StoreT>,
	accessor: (value: Immutable<StoreT>) => Immutable<SubStoreT>,
	callback: (value: Immutable<SubStoreT>) => void
) {
	let value = accessor(store.get());
	callback(value);
	onDestroy(
		store.subscribe((storeVal) => {
			const newValue = accessor(storeVal);
			if (value === newValue) {
				return;
			}
			value = newValue;
			callback(newValue);
		})
	);
}
