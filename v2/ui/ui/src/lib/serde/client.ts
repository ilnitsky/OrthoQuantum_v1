import typia from 'typia';
import type { SubmitQuery } from "../dbTypes";
export const serializeInput = (input: SubmitQuery): string => {
    const $string = (typia.createStringify as any).string;
    const $io1 = (input: any): boolean => (undefined === input.taxon_id || "string" === typeof input.taxon_id) && (undefined === input.species || "number" === typeof input.species) && "string" === typeof input.query && "number" === typeof input.max_prots && ("object" === typeof input.blast && null !== input.blast && $io2(input.blast)) && "boolean" === typeof input.auto_select && (Array.isArray(input.multi_ortho_selection) && input.multi_ortho_selection.every((elem: any) => "string" === typeof elem));
    const $io2 = (input: any): boolean => "boolean" === typeof input.enabled && "string" === typeof input.evalue && ("number" === typeof input.pident && 0 <= input.pident && 100 >= input.pident) && ("number" === typeof input.qcov && 0 <= input.qcov && 100 >= input.qcov);
    const $so0 = (input: any): any => `{"title":${$string(input.title)},"input":${$so1(input.input)}}`;
    const $so1 = (input: any): any => `{${undefined === input.taxon_id ? "" : `"taxon_id":${undefined !== input.taxon_id ? $string(input.taxon_id) : undefined},`}${undefined === input.species ? "" : `"species":${undefined !== input.species ? input.species : undefined},`}"query":${$string(input.query)},"max_prots":${input.max_prots},"blast":${$so2(input.blast)},"auto_select":${input.auto_select},"multi_ortho_selection":${`[${input.multi_ortho_selection.map((elem: any) => $string(elem)).join(",")}]`}}`;
    const $so2 = (input: any): any => `{"enabled":${input.enabled},"evalue":${$string(input.evalue)},"pident":${input.pident},"qcov":${input.qcov}}`;
    return $so0(input);
};
