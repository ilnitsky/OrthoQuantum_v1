import { defaultQuery, type InitData, type Query } from '$lib/dbTypes';
import { getFullData } from '$lib/server/db';
import type { PageServerLoad } from './$types';

type Data = {
	data: InitData<Query>,
	showTutorial: boolean
}

export const load = (async ({ params }): Promise<InitData<Query>> => {
	if (params.qid === 'new') {
		return {
			data: defaultQuery,
			ts: '0',
		};
	}
	const [result] = await Promise.all([getFullData(params.qid)])
	result.data.input = { ...defaultQuery.input, ...result.data.input };
	result.data.output = { ...defaultQuery.output, ...result.data.output };

	return result;
}) satisfies PageServerLoad;
