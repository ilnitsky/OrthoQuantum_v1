import typia from 'typia';
import type { SubmitQuery } from '../dbTypes';
import type { Request as SetTutorialRequest } from '../../routes/api/setTutorial/+server';
import type { Request as SetTitleRequest } from '../../routes/api/setTitle/+server';
import type { Response as GetQueriesResponse } from '../../routes/api/getQueries/+server';
import type { Response as GetSpeciesResponse } from '../../routes/api/getSpecies/+server';
import { error } from '@sveltejs/kit';
import { Ulid } from '../server/db';
import { ObjectId } from 'mongodb';

typia.customValidators.insert('ulid')('string')(() => (value: string) => Ulid.isCanonical(value));
typia.customValidators.insert('ObjectId')('string')(
	() => (value: string) => ObjectId.isValid(value)
);
typia.customValidators.insert('nonempty')('string')(
	() => (value: string) => value.trim().length > 0
);

function errmap<T>(parser: (input: unknown) => T): (req: Request) => Promise<T> {
	return async (req: Request) => {
		try {
			return parser(JSON.parse(await req.text()));
		} catch {
			throw error(400, 'bad request');
		}
	};
}

export const deserializeInput = errmap(typia.createAssertEquals<SubmitQuery>());
export const deserializeSetTutorialRequest = errmap(typia.createAssertEquals<SetTutorialRequest>());
export const deserializeSetTitleRequest = errmap(typia.createAssertEquals<SetTitleRequest>());
export const serializeGetQueriesResponse = typia.createStringify<GetQueriesResponse>();
export const serializeGetSpeciesResponse = typia.createStringify<GetSpeciesResponse>();
