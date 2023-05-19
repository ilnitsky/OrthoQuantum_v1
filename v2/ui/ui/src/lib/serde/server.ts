import typia from 'typia';
import type { SubmitQuery } from "../dbTypes";
import type { Request as SetTutorialRequest } from "../../routes/api/setTutorial/+server";
import type { Request as SetTitleRequest } from "../../routes/api/setTitle/+server";
import type { Response as GetQueriesResponse } from "../../routes/api/getQueries/+server";
import type { Response as GetSpeciesResponse } from "../../routes/api/getSpecies/+server";
import { error } from '@sveltejs/kit';
import { Ulid } from "../server/db";
import { ObjectId } from 'mongodb';
typia.customValidators.insert('ulid')('string')(() => (value: string) => Ulid.isCanonical(value));
typia.customValidators.insert('ObjectId')('string')(() => (value: string) => ObjectId.isValid(value));
typia.customValidators.insert('nonempty')('string')(() => (value: string) => value.trim().length > 0);
function errmap<T>(parser: (input: unknown) => T): (req: Request) => Promise<T> {
    return async (req: Request) => {
        try {
            return parser(JSON.parse(await req.text()));
        }
        catch {
            throw error(400, 'bad request');
        }
    };
}
export const deserializeInput = errmap((input: any): SubmitQuery => {
    const $guard = (typia.createAssertEquals as any).guard;
    const $join = (typia.createAssertEquals as any).join;
    const __is = (input: any, _exceptionable: boolean = true): input is SubmitQuery => {
        const $io0 = (input: any, _exceptionable: boolean = true): boolean => "string" === typeof input.title && ("object" === typeof input.input && null !== input.input && $io1(input.input, true && _exceptionable)) && (2 === Object.keys(input).length || Object.keys(input).every(key => {
            if (["title", "input"].some(prop => key === prop))
                return true;
            const value = input[key];
            if (undefined === value)
                return true;
            return false;
        }));
        const $io1 = (input: any, _exceptionable: boolean = true): boolean => (undefined === input.taxon_id || "string" === typeof input.taxon_id) && (undefined === input.species || "number" === typeof input.species) && "string" === typeof input.query && "number" === typeof input.max_prots && ("object" === typeof input.blast && null !== input.blast && $io2(input.blast, true && _exceptionable)) && "boolean" === typeof input.auto_select && (Array.isArray(input.multi_ortho_selection) && input.multi_ortho_selection.every((elem: any, _index1: number) => "string" === typeof elem)) && (5 === Object.keys(input).length || Object.keys(input).every(key => {
            if (["taxon_id", "species", "query", "max_prots", "blast", "auto_select", "multi_ortho_selection"].some(prop => key === prop))
                return true;
            const value = input[key];
            if (undefined === value)
                return true;
            return false;
        }));
        const $io2 = (input: any, _exceptionable: boolean = true): boolean => "boolean" === typeof input.enabled && "string" === typeof input.evalue && ("number" === typeof input.pident && 0 <= input.pident && 100 >= input.pident) && ("number" === typeof input.qcov && 0 <= input.qcov && 100 >= input.qcov) && (4 === Object.keys(input).length || Object.keys(input).every(key => {
            if (["enabled", "evalue", "pident", "qcov"].some(prop => key === prop))
                return true;
            const value = input[key];
            if (undefined === value)
                return true;
            return false;
        }));
        return "object" === typeof input && null !== input && $io0(input, true);
    };
    if (false === __is(input))
        ((input: any, _path: string, _exceptionable: boolean = true): input is SubmitQuery => {
            const $ao0 = (input: any, _path: string, _exceptionable: boolean = true): boolean => ("string" === typeof input.title || $guard(_exceptionable, {
                path: _path + ".title",
                expected: "string",
                value: input.title
            })) && (("object" === typeof input.input && null !== input.input || $guard(_exceptionable, {
                path: _path + ".input",
                expected: "Resolve<Input>",
                value: input.input
            })) && $ao1(input.input, _path + ".input", true && _exceptionable)) && (2 === Object.keys(input).length || (false === _exceptionable || Object.keys(input).every(key => {
                if (["title", "input"].some(prop => key === prop))
                    return true;
                const value = input[key];
                if (undefined === value)
                    return true;
                return $guard(_exceptionable, {
                    path: _path + $join(key),
                    expected: "undefined",
                    value: value
                });
            })));
            const $ao1 = (input: any, _path: string, _exceptionable: boolean = true): boolean => (undefined === input.taxon_id || "string" === typeof input.taxon_id || $guard(_exceptionable, {
                path: _path + ".taxon_id",
                expected: "(string | undefined)",
                value: input.taxon_id
            })) && (undefined === input.species || "number" === typeof input.species || $guard(_exceptionable, {
                path: _path + ".species",
                expected: "(number | undefined)",
                value: input.species
            })) && ("string" === typeof input.query || $guard(_exceptionable, {
                path: _path + ".query",
                expected: "string",
                value: input.query
            })) && ("number" === typeof input.max_prots || $guard(_exceptionable, {
                path: _path + ".max_prots",
                expected: "number",
                value: input.max_prots
            })) && (("object" === typeof input.blast && null !== input.blast || $guard(_exceptionable, {
                path: _path + ".blast",
                expected: "Resolve<__type>",
                value: input.blast
            })) && $ao2(input.blast, _path + ".blast", true && _exceptionable)) && ("boolean" === typeof input.auto_select || $guard(_exceptionable, {
                path: _path + ".auto_select",
                expected: "boolean",
                value: input.auto_select
            })) && ((Array.isArray(input.multi_ortho_selection) || $guard(_exceptionable, {
                path: _path + ".multi_ortho_selection",
                expected: "Array<string>",
                value: input.multi_ortho_selection
            })) && input.multi_ortho_selection.every((elem: any, _index1: number) => "string" === typeof elem || $guard(_exceptionable, {
                path: _path + ".multi_ortho_selection[" + _index1 + "]",
                expected: "string",
                value: elem
            }))) && (5 === Object.keys(input).length || (false === _exceptionable || Object.keys(input).every(key => {
                if (["taxon_id", "species", "query", "max_prots", "blast", "auto_select", "multi_ortho_selection"].some(prop => key === prop))
                    return true;
                const value = input[key];
                if (undefined === value)
                    return true;
                return $guard(_exceptionable, {
                    path: _path + $join(key),
                    expected: "undefined",
                    value: value
                });
            })));
            const $ao2 = (input: any, _path: string, _exceptionable: boolean = true): boolean => ("boolean" === typeof input.enabled || $guard(_exceptionable, {
                path: _path + ".enabled",
                expected: "boolean",
                value: input.enabled
            })) && ("string" === typeof input.evalue || $guard(_exceptionable, {
                path: _path + ".evalue",
                expected: "string",
                value: input.evalue
            })) && ("number" === typeof input.pident && (0 <= input.pident || $guard(_exceptionable, {
                path: _path + ".pident",
                expected: "number (@minimum 0)",
                value: input.pident
            })) && (100 >= input.pident || $guard(_exceptionable, {
                path: _path + ".pident",
                expected: "number (@maximum 100)",
                value: input.pident
            })) || $guard(_exceptionable, {
                path: _path + ".pident",
                expected: "number",
                value: input.pident
            })) && ("number" === typeof input.qcov && (0 <= input.qcov || $guard(_exceptionable, {
                path: _path + ".qcov",
                expected: "number (@minimum 0)",
                value: input.qcov
            })) && (100 >= input.qcov || $guard(_exceptionable, {
                path: _path + ".qcov",
                expected: "number (@maximum 100)",
                value: input.qcov
            })) || $guard(_exceptionable, {
                path: _path + ".qcov",
                expected: "number",
                value: input.qcov
            })) && (4 === Object.keys(input).length || (false === _exceptionable || Object.keys(input).every(key => {
                if (["enabled", "evalue", "pident", "qcov"].some(prop => key === prop))
                    return true;
                const value = input[key];
                if (undefined === value)
                    return true;
                return $guard(_exceptionable, {
                    path: _path + $join(key),
                    expected: "undefined",
                    value: value
                });
            })));
            return ("object" === typeof input && null !== input || $guard(true, {
                path: _path + "",
                expected: "Resolve<SubmitQuery>",
                value: input
            })) && $ao0(input, _path + "", true);
        })(input, "$input", true);
    return input;
});
export const deserializeSetTutorialRequest = errmap((input: any): SetTutorialRequest => {
    const $guard = (typia.createAssertEquals as any).guard;
    const $join = (typia.createAssertEquals as any).join;
    const __is = (input: any, _exceptionable: boolean = true): input is SetTutorialRequest => {
        const $io0 = (input: any, _exceptionable: boolean = true): boolean => "boolean" === typeof input.showTutorial && (1 === Object.keys(input).length || Object.keys(input).every(key => {
            if (["showTutorial"].some(prop => key === prop))
                return true;
            const value = input[key];
            if (undefined === value)
                return true;
            return false;
        }));
        return "object" === typeof input && null !== input && $io0(input, true);
    };
    if (false === __is(input))
        ((input: any, _path: string, _exceptionable: boolean = true): input is SetTutorialRequest => {
            const $ao0 = (input: any, _path: string, _exceptionable: boolean = true): boolean => ("boolean" === typeof input.showTutorial || $guard(_exceptionable, {
                path: _path + ".showTutorial",
                expected: "boolean",
                value: input.showTutorial
            })) && (1 === Object.keys(input).length || (false === _exceptionable || Object.keys(input).every(key => {
                if (["showTutorial"].some(prop => key === prop))
                    return true;
                const value = input[key];
                if (undefined === value)
                    return true;
                return $guard(_exceptionable, {
                    path: _path + $join(key),
                    expected: "undefined",
                    value: value
                });
            })));
            return ("object" === typeof input && null !== input || $guard(true, {
                path: _path + "",
                expected: "Resolve<Request>",
                value: input
            })) && $ao0(input, _path + "", true);
        })(input, "$input", true);
    return input;
});
export const deserializeSetTitleRequest = errmap((input: any): SetTitleRequest => {
    const $guard = (typia.createAssertEquals as any).guard;
    const $is_custom = (typia.createAssertEquals as any).is_custom;
    const $join = (typia.createAssertEquals as any).join;
    const __is = (input: any, _exceptionable: boolean = true): input is SetTitleRequest => {
        const $is_custom = (typia.createAssertEquals as any).is_custom;
        const $io0 = (input: any, _exceptionable: boolean = true): boolean => "string" === typeof input.qid && $is_custom("ulid", "string", "", input.qid) && ("string" === typeof input.title && $is_custom("nonempty", "string", "", input.title)) && (2 === Object.keys(input).length || Object.keys(input).every(key => {
            if (["qid", "title"].some(prop => key === prop))
                return true;
            const value = input[key];
            if (undefined === value)
                return true;
            return false;
        }));
        return "object" === typeof input && null !== input && $io0(input, true);
    };
    if (false === __is(input))
        ((input: any, _path: string, _exceptionable: boolean = true): input is SetTitleRequest => {
            const $ao0 = (input: any, _path: string, _exceptionable: boolean = true): boolean => ("string" === typeof input.qid && ($is_custom("ulid", "string", "", input.qid) || $guard(_exceptionable, {
                path: _path + ".qid",
                expected: "string (@ulid)",
                value: input.qid
            })) || $guard(_exceptionable, {
                path: _path + ".qid",
                expected: "string",
                value: input.qid
            })) && ("string" === typeof input.title && ($is_custom("nonempty", "string", "", input.title) || $guard(_exceptionable, {
                path: _path + ".title",
                expected: "string (@nonempty)",
                value: input.title
            })) || $guard(_exceptionable, {
                path: _path + ".title",
                expected: "string",
                value: input.title
            })) && (2 === Object.keys(input).length || (false === _exceptionable || Object.keys(input).every(key => {
                if (["qid", "title"].some(prop => key === prop))
                    return true;
                const value = input[key];
                if (undefined === value)
                    return true;
                return $guard(_exceptionable, {
                    path: _path + $join(key),
                    expected: "undefined",
                    value: value
                });
            })));
            return ("object" === typeof input && null !== input || $guard(true, {
                path: _path + "",
                expected: "Resolve<Request>",
                value: input
            })) && $ao0(input, _path + "", true);
        })(input, "$input", true);
    return input;
});
export const serializeGetQueriesResponse = (input: GetQueriesResponse): string => {
    const $string = (typia.createStringify as any).string;
    const $io1 = (input: any): boolean => "string" === typeof input.title && "string" === typeof input.qid;
    const $so0 = (input: any): any => `{"ok":${input.ok},"data":${`[${input.data.map((elem: any) => `{"title":${$string(elem.title)},"qid":${$string(elem.qid)}}`).join(",")}]`}}`;
    return $so0(input);
};
export const serializeGetSpeciesResponse = (input: GetSpeciesResponse): string => {
    const $string = (typia.createStringify as any).string;
    const $io1 = (input: any): boolean => "string" === typeof input.taxon_id && (Array.isArray(input.species) && input.species.every((elem: any) => "object" === typeof elem && null !== elem && $io2(elem)));
    const $io2 = (input: any): boolean => "string" === typeof input.name && "number" === typeof input.taxid;
    const $so0 = (input: any): any => `{"ok":${input.ok},"data":${`[${input.data.map((elem: any) => $so1(elem)).join(",")}]`}}`;
    const $so1 = (input: any): any => `{"taxon_id":${$string(input.taxon_id)},"species":${`[${input.species.map((elem: any) => `{"name":${$string(elem.name)},"taxid":${elem.taxid}}`).join(",")}]`}}`;
    return $so0(input);
};
