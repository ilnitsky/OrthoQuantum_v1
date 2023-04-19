import type { InitData, Query, Species, Taxon } from '$lib/dbTypes';
import { getFullData, getSpecies, getTaxons } from '$lib/server/db';
import type { PageServerLoad } from './$types';

type Data = {
	pageData: InitData<Query>;
	taxons: Taxon[];
	species?: Species;
	showTutorial: boolean;
};

export const load = (async ({ params }): Promise<Data> => {
	console.time('Query page load');
	const [pageData, taxons] = await Promise.all([getFullData(params.qid), getTaxons()]);
	const result = {
		pageData,
		taxons,
		showTutorial: false // TODO: grab from user's account in DB
	} as Data;
	if (pageData.data.input.taxon_id) {
		result.species = await getSpecies(pageData.data.input.taxon_id);
	}
	console.timeEnd('Query page load');
	return result;
}) satisfies PageServerLoad;
