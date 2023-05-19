import type { Taxon } from '$lib/dbTypes';
import { getFullData, getSpecies, taxons } from '$lib/server/db';
import { ObjectId } from 'mongodb';
import type { PageServerLoad } from './$types';
import { authenticateUser } from '$lib/server/validation';

async function getTaxons() {
	console.time('getTaxons');
	const req = taxons.find<Taxon>(
		{},
		{
			sort: { priority: -1, name: 1 },
			projection: { _id: 0, name: 1, id: { $toString: '$_id' } },
		}
	);
	const data = await req.toArray();

	console.timeEnd('getTaxons');
	return data;
}

export const load = (async (req) => {
	console.time('Query page load');
	const [user, [query, ts], taxons] = await Promise.all([
		authenticateUser(req, true),
		getFullData(req.params.qid),
		getTaxons(),
	]);
	const result = {
		query,
		ts,
		taxons,
		showTutorial: user?.showTutorial ?? true,
		species: query.input.taxon_id ? await getSpecies(new ObjectId(query.input.taxon_id)) : [],
	};
	console.timeEnd('Query page load');
	return result;
}) satisfies PageServerLoad;
