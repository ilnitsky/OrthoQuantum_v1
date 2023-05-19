import type { Data, TimestampedData } from '$lib/dbTypes';
import type { Patch } from 'immer';
import type {
	Document,
	ChangeStream,
	ChangeStreamDocument,
	UpdateDescription,
} from 'mongodb';

export const ClientUninterested = Symbol('ClientUninterested');
export const Invalidate = Symbol('MongoInvalidate');

const retryTimeoutMs = 300;

const validPaths = ['input', 'output', 'title'];
function formatChanges(upd: UpdateDescription<Document>): Patch[] {
	const paths = upd.disambiguatedPaths || {};
	const updates: Patch[] = [];
	function getPath(path: string): string[] {
		return paths[path] || path.split('.');
	}
	for (const [key, val] of Object.entries(upd.updatedFields || {})) {
		const path = getPath(key);
		if (validPaths.includes(path[0])) {
			updates.push({ op: 'add', path: path, value: val });
		}
	}
	for (const item of upd.removedFields || []) {
		const path = getPath(item);
		if (validPaths.includes(path[0])) {
			updates.push({ op: 'remove', path: path });
		}
	}
	for (const item of upd.truncatedArrays || []) {
		const path = getPath(item.field);
		if (validPaths.includes(path[0])) {
			updates.push({ op: 'add', path: path, value: item.newSize });
		}
	}
	return updates;
}

export class SSESender<D extends Data> {
	controller: ReadableStreamDefaultController<unknown>;
	startTime: string;
	// reject when client goes out
	#clientInterested: Promise<never>;
	#getUpdates: (startTime: string) => ChangeStream<Document, ChangeStreamDocument<Document>>;
	#getFullData: () => Promise<TimestampedData<D>>;

	constructor(
		startTime: string,
		controller: ReadableStreamDefaultController<unknown>,
		clientInterested: Promise<never>,
		getUpdates: (startTime: string) => ChangeStream<Document, ChangeStreamDocument<Document>>,
		getFullData: () => Promise<TimestampedData<D>>
	) {
		console.log('SSE from', startTime);
		this.startTime = startTime;
		this.controller = controller;
		this.#clientInterested = clientInterested;
		this.#getUpdates = getUpdates;
		this.#getFullData = getFullData;
	}

	async updates() {
		let cursor: ChangeStream<Document, ChangeStreamDocument<Document>> | undefined;
		try {
			cursor = this.#getUpdates(this.startTime);
			// eslint-disable-next-line no-constant-condition
			while (true) {
				const doc = await Promise.race([this.#clientInterested, cursor.next()]);
				// console.log('DB update', doc);
				switch (doc.operationType) {
					case 'update':
						{
							if (doc.clusterTime) {
								this.startTime = doc.clusterTime.add(1).toString();
							}
							const updates = formatChanges(doc.updateDescription);
							if (updates.length != 0) {
								this.controller.enqueue(
									`id: ${this.startTime}\ndata: ${JSON.stringify(updates)}\n\n`
								);
							}
						}
						break;
					case 'replace':
						{
							if (doc.clusterTime) {
								this.startTime = doc.clusterTime.add(1).toString();
							}
							const update = {
								title: doc.fullDocument.title,
								input: doc.fullDocument.input,
								output: doc.fullDocument.output,
							};
							this.controller.enqueue(
								`id: ${this.startTime}\nevent: fullData\ndata: ${JSON.stringify(update)}\n\n`
							);
						}
						break;
					case 'invalidate':
						throw Invalidate;
				}
			}
		} finally {
			await cursor?.close();
		}
	}

	async updateLoop(firstConnect: boolean) {
		if (firstConnect) {
			// Not a reconnect, set retry interval
			this.controller.enqueue(`retry: ${retryTimeoutMs}\n\n`);
		}
		let restartCount = 0;
		const maxRestarts = 5;
		while (restartCount < maxRestarts) {
			try {
				await this.updates();
			} catch (err: unknown) {
				if (err === ClientUninterested) {
					return;
				}

				restartCount += 1;
				setTimeout(() => {
					restartCount -= 1;
				}, 5000);

				if (restartCount === maxRestarts) {
					throw err;
				}
				if (err !== Invalidate) {
					console.error(err);
				}
				if (err === Invalidate || restartCount === 3 || restartCount === 4) {
					const [data, ts] = await Promise.race([this.#clientInterested, this.#getFullData()]);
					this.startTime = ts;
					this.controller.enqueue(
						`id: ${this.startTime}\nevent: fullData\ndata: ${JSON.stringify(data)}\n\n`
					);
				}
			}
		}
	}
}
