// TODO: must be server-only
import {
	HIDDEN,
	type InitData,
	type ProgressBar,
	type Query,
	type Species,
	type Taxon
} from '$lib/dbTypes';
import { Collection, MongoClient, ObjectId, Timestamp } from 'mongodb';

const client = new MongoClient(
	'mongodb+srv://mongodbweb:hzmyV4PbeKfckSqA@cluster0.tgy4v7h.mongodb.net/test'
);
const db = client.db('db');
const coll = db.collection('data') as Collection<Query>;
type TaxonsDoc = {
	name: string;
	priority: number;
	species: {
		name: string;
		taxid: number;
	}[];
};
const taxons = db.collection('taxons') as Collection<TaxonsDoc>;

const defaultPB: ProgressBar = {
	kind: HIDDEN,
	message: '',
	val: 0,
	max: 0
};
export const defaultQuery: Query = {
	input: {
		title: 'New Query',
		taxon_id: '640c8db34885b8212709fd4d', // TODO: set to vertebrata
		species: 1,
		query: 'Some query',
		max_prots: 650,
		blast: {
			enabled: false,
			evalue: '1e-5',
			seqident: 80,
			qcov: 80
		},
		auto_select: true,
		multi_ortho_selection: null
	},
	output: {
		rid: '',
		unknown_proteins: [],
		multi_ortho: [],
		progress_prottable: defaultPB,
		progress_heatmap: defaultPB,
		prot_table_data: [],
		missing_uniprot: [],
		corr_map_ver: '',
		corr_table: [],
		progress_tree: defaultPB,
		tree: {
			version: '',
			blasted: 0
		}
	}
};

export async function getTaxons() {
	const req = taxons.aggregate([
		{ $sort: { priority: 1, name: -1 } },
		{ $project: { priority: 0, species: 0 } }
	]);
	const data = await req.toArray();
	for (const item of data) {
		item.id = item._id.toString();
		delete item._id;
	}
	return data as Taxon[];
}

export async function getSpecies(taxonId: string) {
	const species = (await taxons.findOne(
		{
			_id: new ObjectId(taxonId)
		},
		{
			projection: { _id: 1, species: 1 }
		}
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
	)) as any;
	if (!species) {
		throw new Error('No speceis found');
	}
	species.taxon_id = species._id.toString();
	delete species._id;
	return species as Species;
}

export async function getAllSpecies() {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const species: any[] = await taxons
		.find(
			{},
			{
				projection: { name: 0, priority: 0 }
			}
		)
		.toArray();
	if (!species.length) {
		throw new Error('No speceis found');
	}
	for (const it of species) {
		it.taxon_id = it._id.toString();
		delete it._id;
	}
	return species as Species[];
}

export async function getFullData(qid: ObjectId | string): Promise<InitData<Query>> {
	let cursor;
	if (qid === 'new') {
		return Promise.resolve({
			data: defaultQuery,
			ts: '0'
		});
	}
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
			{ $project: { _id: 0, input: 1, output: 1 } },
			{ $replaceWith: { data: '$$ROOT', ts: '$$CLUSTER_TIME' } }
		]);
		const result = await cursor.next();
		if (!result) {
			throw new Error('No data');
		}

		result.ts = result.ts.toString();
		console.timeEnd('db req');

		result.data.input = { ...defaultQuery.input, ...result.data.input };
		result.data.output = { ...defaultQuery.output, ...result.data.output };

		return result as InitData<Query>;
	} finally {
		await cursor?.close();
	}
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
