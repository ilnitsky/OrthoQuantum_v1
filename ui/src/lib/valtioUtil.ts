import { subscribe, snapshot } from 'valtio/vanilla';
export { proxy } from 'valtio/vanilla';
import { subscribeKey } from 'valtio/vanilla/utils';
import type { Readable } from 'svelte/store';

export function toStore<T extends object>(proxyState: T): Readable<ReturnType<typeof snapshot<T>>> {
	return {
		subscribe(set) {
			set(snapshot(proxyState));

			return subscribe(proxyState, () => {
				set(snapshot(proxyState));
			});
		}
	};
}

export function keyToStore<T extends object, K extends keyof T>(
	proxyState: T,
	key: K
): Readable<T[K]> {
	return {
		subscribe(set) {
			set(proxyState[key]);

			return subscribeKey(proxyState, key, (newValue) => {
				set(newValue);
			});
		}
	};
}
