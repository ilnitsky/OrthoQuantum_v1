// TODO: must be server-only
import type { InitData, Query } from '$lib/dbTypes';
import { Collection, MongoClient, ObjectId, Timestamp } from 'mongodb';

const client = new MongoClient(
	'mongodb+srv://mongodbweb:hzmyV4PbeKfckSqA@cluster0.tgy4v7h.mongodb.net/test'
);
const db = client.db('db');
const coll = db.collection('data') as Collection<Query>;

export async function getFullData(qid: ObjectId | string): Promise<InitData<Query>> {
	let cursor;
	if (typeof qid === 'string') {
		qid = new ObjectId(qid);
	}
	try {
		console.time('db req');
		cursor = coll.aggregate([
			{
				$match: {
					_id: qid
				}
			},
			{ $project: { _id: 0 } },
			{ $replaceWith: { data: '$$ROOT', ts: '$$CLUSTER_TIME' } }
		]);
		const result = await cursor.next();
		if (!result) {
			throw new Error('No data');
		}

		result.ts = result.ts.toString();
		console.timeEnd('db req');
		return result as InitData<Query>;
	} finally {
		await cursor?.close();
	}
}
export async function newQuery() {
	// coll.insertOne();
}

export function getUpdates(qid: ObjectId | string, changeStreamStart: string) {
	if (typeof qid === 'string') {
		qid = new ObjectId(qid);
	}
	return coll.watch(
		[
			{
				$match: {
					operationType: { $in: ['update', 'invalidate', 'replace'] },
					documentKey: { _id: qid }
				}
			},
			{
				$project: {
					clusterTime: 1,
					updateDescription: 1,
					operationType: 1,
					fullDocument: 1
				}
			}
		],
		{
			startAtOperationTime: Timestamp.fromString(changeStreamStart, 10)
		}
	);
}

export async function setTitle(qid: ObjectId | string, title: string) {
	if (typeof qid === 'string') {
		qid = new ObjectId(qid);
	}
	return coll.updateOne(
		{
			_id: qid
		},
		{
			$set: {
				'input.title': title
			}
		}
	);
}
