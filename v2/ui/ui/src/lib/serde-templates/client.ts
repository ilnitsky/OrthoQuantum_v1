import typia from 'typia';
import type { SubmitQuery } from '../dbTypes';

export const serializeInput = typia.createStringify<SubmitQuery>();
