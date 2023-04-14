import type { Data, InitData } from "$lib/dbTypes";
import type { Document, ChangeStream, ChangeStreamDocument } from "mongodb";

export const ClientUninterested = Symbol('ClientUninterested');
export const Invalidate = Symbol('MongoInvalidate');

const retryTimeoutMs = 300;

export class SSESender<D extends Data> {
	controller: ReadableStreamDefaultController<unknown>;
	startTime: string;
	// reject when client goes out
	#clientInterested: Promise<never>;
  #getUpdates: (startTime: string)=>ChangeStream<Document, ChangeStreamDocument<Document>>;
  #getFullData: ()=>Promise<InitData<D>>;

	constructor(
		startTime: string,
		controller: ReadableStreamDefaultController<unknown>,
		clientInterested: Promise<never>,
    getUpdates: (startTime: string)=>ChangeStream<Document, ChangeStreamDocument<Document>>,
    getFullData: ()=>Promise<InitData<D>>,
	) {
		console.log('SSE from', startTime);
		this.startTime = startTime;
		this.controller = controller;
		this.#clientInterested = clientInterested;
    this.#getUpdates = getUpdates;
    this.#getFullData = getFullData;
	}

	async updates() {
		const cursor = this.#getUpdates(this.startTime);
		try {
			while (await Promise.race([this.#clientInterested, cursor.hasNext()])) {
				const doc = await cursor.next();
				console.log("DB update", doc);
				switch (doc.operationType) {
					case 'update':
						if (doc.clusterTime) {
							this.startTime = doc.clusterTime.add(1).toString();
						}
						this.controller.enqueue(
							`id: ${this.startTime}\ndata: ${JSON.stringify(doc.updateDescription)}\n\n`
						);
						break;
          case 'replace':
            if (doc.clusterTime) {
							this.startTime = doc.clusterTime.add(1).toString();
						}
            delete doc.fullDocument["_id"];
						this.controller.enqueue(
							`id: ${this.startTime}\nevent: fullData\ndata: ${JSON.stringify(doc.fullDocument)}\n\n`
						);
						break;
					case 'invalidate':
						throw Invalidate;
				}
			}
		}
    finally {
			await cursor.close();
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
					const data = await Promise.race([this.#clientInterested, this.#getFullData()]);
					this.startTime = data.ts;
					this.controller.enqueue(
						`id: ${this.startTime}\nevent: fullData\ndata: ${JSON.stringify(data.data)}\n\n`
					);
				}
			}
		}
	}
}


