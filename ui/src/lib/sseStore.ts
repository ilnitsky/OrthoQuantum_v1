import { subscribe, snapshot, proxy } from 'valtio/vanilla';
export { proxy } from 'valtio/vanilla';
import { subscribeKey, devtools } from 'valtio/vanilla/utils';
import type { Readable, Writable } from 'svelte/store';

import diff from 'recursive-diff';
import type { UpdateDescription } from 'mongodb';
import { onMount } from 'svelte';
import type { Data, InitData, Store } from './dbTypes';
import { dev } from '$app/environment';

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


class SSEStore<T extends Data> {
	store: Store<T>;
	lastEventId: string;
	stop: () => void;
	#url: URL;
	#sse: EventSource | undefined;
	#unsubTimer: ReturnType<typeof setTimeout> | undefined;

	constructor(url: URL, store: Store<T>, lastEventId: string) {
		this.store = store;
		this.lastEventId = lastEventId;
		this.#url = new URL(url);

		this.#subscribe();
		const handler = this.#onvisibilitychange.bind(this);
		document.addEventListener('visibilitychange', handler);
		this.stop = () => {
			document.removeEventListener('visibilitychange', this.#onvisibilitychange);
			this.#unsubscribe();
		};
	}

	#onvisibilitychange() {
		switch (document.visibilityState) {
			case 'visible':
				this.#subscribe();
				break;
			case 'hidden':
				// unsubscribe if the page is hidden for a bit, since SSE have strict limits on open connections
				this.#unsubTimer = setTimeout(this.#unsubscribe.bind(this), 30 * 1000);
				break;
		}
	}

	// update proxy based on sse
	#onFullData(ev: MessageEvent<string>) {
		const update = JSON.parse(ev.data) as T;
		// Applying as diff to avoid replacing objects, otherwise wont trigger state updates
		if (update.input){
			diff.applyDiff(this.store.input, diff.getDiff(this.store.input, update.input));
			this.store.db_input = update.input;
		}
		if (update.output){
			diff.applyDiff(this.store.output, diff.getDiff(this.store.output, update.output));
		}
		this.lastEventId = ev.lastEventId;
	}

	// applies updates to nesessary items in state
	#onChangeData(ev: MessageEvent<string>) {
		const update = JSON.parse(ev.data) as UpdateDescription;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		let obj: any;
		for (const [field, value] of Object.entries(update.updatedFields ?? {})) {
			const path = field.split('.');
			obj = this.store;
			for (let i = 0; i < path.length - 1; i++) {
				obj = obj[path[i]];
			}
			obj[path[path.length - 1]] = value;
			if (path[0] === "input"){
				obj = this.store.db_input;
				for (let i = 1; i < path.length - 1; i++) {
					obj = obj[path[i]];
				}
				obj[path[path.length - 1]] = value;
			}
		}
		for (const field of update.removedFields ?? []) {
			const path = field.split('.');
			obj = this.store;
			for (let i = 0; i < path.length - 1; i++) {
				obj = obj[path[i]];
			}
			delete obj[path[path.length - 1]];
			if (path[0] === "input"){
				obj = this.store.db_input;
				for (let i = 1; i < path.length - 1; i++) {
					obj = obj[path[i]];
				}
				delete obj[path[path.length - 1]];
			}
		}
		for (const { field, newSize } of update.truncatedArrays ?? []) {
			const path = field.split('.');
			obj = this.store;
			for (let i = 0; i < path.length; i++) {
				obj = obj[path[i]];
			}
			obj.length = newSize;
			if (path[0] === "input"){
				obj = this.store.db_input;
				for (let i = 1; i < path.length; i++) {
					obj = obj[path[i]];
				}
				obj.length = newSize;
			}
		}
		console.log("SSE Update", update, this.store)
		this.lastEventId = ev.lastEventId;
	}

	#subscribe() {
		clearTimeout(this.#unsubTimer);
		this.#unsubTimer = undefined;
		if (this.#sse) {
			return;
		}
		this.#url.search = `?sse=${this.lastEventId}`;
		this.#sse = new EventSource(this.#url, { withCredentials: true });
		this.#sse.addEventListener('message', this.#onChangeData.bind(this));
		this.#sse.addEventListener('fullData', this.#onFullData.bind(this));
		this.#sse.onopen = (e)=>{
			console.log("SSE open", e);
		}
		this.#sse.onerror = (e)=>{
			console.log("SSE error", e);
		}
	}

	#unsubscribe() {
		clearTimeout(this.#unsubTimer);
		this.#unsubTimer = undefined;
		if (!this.#sse) {
			return;
		}
		this.#sse.close();
		this.#sse = undefined;
	}
}

export function initStore<D extends Data>(data: InitData<D>, pageUrl: URL, isNew: boolean): Store<D> {
	const state = {
		// Reflects the state stored in the db, updates via SSE
		db_input: data.data.input,
		// Reflects user's modifications to the state,
		// updated by user changes and SSE
		input: proxy(data.data.input),
		output: proxy(data.data.output)
	} as Store<D>;

	onMount(() => {
		const callbacks: ((() => void) | undefined)[] = [];
		if (!isNew){
			const sse = new SSEStore(pageUrl, state, data.ts);
			callbacks.push(sse.stop);
		}

		if (dev) {
			callbacks.push(
				devtools(
					proxy({
						input: state.input,
						output: state.output,
					}),
					{ name: 'state', enabled: true }
				)
			);
		}
		return () => {
			callbacks.forEach((f) => f?.());
		};
	});
	return state;
}
