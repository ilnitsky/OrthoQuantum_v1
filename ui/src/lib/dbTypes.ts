// generic
export type Data = {
	/** valtio proxy with user input (combines server data with user's modifications) */
	input: object;
	/** valtio proxy with results from server */
	output: object;
};
export type InitData<T extends Data> = {
	data: T;
	ts: string;
};

export type Store<D extends Data> = D & {
	/** static non-proxy copy of server data */
	db_input: D['input'];
};

export const HIDDEN = 0;
export const QUEUE = 1;
export const ERROR = 2;
export const PROGRESS = 3;

export type Taxon = {
	name: string;
	id: string;
};

export type Species = {
	taxon_id: string;
	species: {
		name: string;
		taxid: number;
	}[];
};

export type ProgressBar = {
	kind: number;
	message: string;
	val: number;
	max: number;
};

export type Query = {
	input: {
		title: string;
		taxon_id: string | null;
		species: number | null;
		query: string;
		max_prots: number;
		blast: {
			enabled: boolean;
			evalue: string;
			seqident: number;
			qcov: number;
		};
		auto_select: boolean;
		multi_ortho_selection: number[] | null;
	};
	output: {
		/** Run id */
		rid: string;
		unknown_proteins: string[];
		multi_ortho: string[][];
		progress_prottable: ProgressBar;
		progress_heatmap: ProgressBar;
		prot_table_data: string[][];
		missing_uniprot: string[];
		/** png image of correlation */
		corr_map_ver: string;
		corr_table: {
			a: string;
			b: string;
			/** correlation */
			c: number;
			/** quantile */
			q: number;
		}[];
		progress_tree: ProgressBar;
		tree: {
			version: string;
			blasted: number;
		};
	};
};
