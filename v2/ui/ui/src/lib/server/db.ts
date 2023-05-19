import {
	HIDDEN,
	type TimestampedData,
	type ProgressBar,
	type Query,
	type Species,
	type DBQuery,
	type DBUser,
	type DBTaxon,
} from '$lib/dbTypes';
import { error } from '@sveltejs/kit';
import { MongoClient, ObjectId, Timestamp, Binary, Collection } from 'mongodb';
import id128 from 'id128';
import { env } from '$env/dynamic/private';
export const Ulid = id128.Ulid;
export type Ulid = ReturnType<typeof id128.Ulid.construct>;

const db_client = new MongoClient(env.MONGO_URL);
const db = db_client.db('db');

export const queries = db.collection<DBQuery>('queries');
export const taxons = db.collection<DBTaxon>('taxons');
export const users = db.collection<DBUser>('users');

const defaultPB: ProgressBar = {
	kind: HIDDEN,
	message: '',
	val: 0,
	max: 0,
};
export const defaultQuery: Query = {
	title: 'New Query',
	input: {
		taxon_id: '640c8db34885b8212709fd4d', // TODO: set to vertebrata
		// species: 1,
		query: '',
		max_prots: 650,
		blast: {
			enabled: false,
			evalue: '1e-5',
			pident: 80,
			qcov: 80,
		},
		auto_select: true,
		multi_ortho_selection: ['2'],
	},
	output: {
		rid: '',
		unknown_proteins: [],
		multi_ortho: [
			[
				'1',
				'SMPDL3A1',
				'1574805at7742',
				'SMPDL3A',
				'sphingomyelin phosphodiesterase acid like 3A',
				'474',
				'462',
			],
			[
				'2',
				'SMPDL3A2',
				'1574805at7742',
				'SMPDL3A',
				'sphingomyelin phosphodiesterase acid like 3A',
				'474',
				'462',
			],
		],
		progress_prottable: defaultPB,
		progress_heatmap: defaultPB,
		prot_table_data: [],
		missing_uniprot: [],
		corr_map_ver: '',
		corr_table: [],
		progress_tree: defaultPB,
		tree: {
			version: '',
			blasted: 0,
		},
	},
};

export async function getSpecies(taxonId?: ObjectId) {
	console.time('getSpecies');
	const species = await taxons
		.find<Species>(taxonId ? { _id: taxonId } : {}, {
			projection: { species: 1, _id: 0, taxon_id: { $toString: '$_id' } },
		})
		.toArray();
	if (species.length == 0) {
		throw error(500, {
			message: 'No speceies found',
		});
	}
	console.timeEnd('getSpecies');
	return species;
}

export async function getFullData(qid: Binary | string): Promise<TimestampedData<Query>> {
	if (qid === 'new') {
		return Promise.resolve([defaultQuery, '0']);
	}
	console.time('getFullData');
	if (typeof qid === 'string') {
		qid = qidCheck(qid);
	}
	const result = (
		await (queries as unknown as Collection<DBQuery & { ts: Timestamp }>).findOneAndUpdate(
			{ _id: qid },
			{ $currentDate: { last_view: true } },
			{ projection: { title: 1, input: 1, output: 1, ts: '$$CLUSTER_TIME' } }
		)
	).value;

	if (!result) {
		throw error(404, {
			message: 'Query not found',
		});
	}
	// setViewed(qid);
	// TODO: remove this or move to client-side
	console.timeEnd('getFullData');
	return [
		{
			title: result.title || defaultQuery.title,
			input: { ...defaultQuery.input, ...result.input },
			output: { ...defaultQuery.output, ...result.output },
		},
		result.ts.toString(),
	];
}

export function qidFormat(qid: Binary): string {
	return Ulid.construct(qid.buffer).toCanonical();
}

export function qidCheck(qid: string): Binary {
	try {
		return new Binary(Ulid.fromCanonical(qid).bytes);
	} catch (err) {
		throw error(404, 'Incorrect query id');
	}
}

export function qidConvertTrusted(qid: string): Binary {
	return new Binary(Ulid.fromCanonicalTrusted(qid).bytes);
}

export function ulidToBin(ulid: Ulid): Binary {
	return new Binary(ulid.bytes);
}
