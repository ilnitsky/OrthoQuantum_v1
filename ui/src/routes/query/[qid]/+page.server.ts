import type { InitData, Query, Species, Taxon } from '$lib/dbTypes';
import { getFullData, getSpecies, getTaxons } from '$lib/server/db';
import type { PageServerLoad } from './$types';

type Data = {
	pageData: InitData<Query>;
	taxons: Taxon[];
	species?: Species;
	// showTutorial: boolean;
};

export const load = (async ({ params }): Promise<Data> => {
	const [pageData, taxons] = await Promise.all([getFullData(params.qid), getTaxons()]);
	const result = {
		pageData,
		taxons
	} as Data;
	if (pageData.data.input.taxon_id) {
		result.species = await getSpecies(pageData.data.input.taxon_id);
	}
	return result;
}) satisfies PageServerLoad;
