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

// export type QueryData = InitData<Query>;
// export type QueryStore = Store<Query>;

const defaultPB: ProgressBar = {
  kind: HIDDEN,
  message: '',
  val: 0,
  max: 0
};
export const defaultQuery: Query = {
  input: {
    title: 'New Query',
    taxon_id: "1", // TODO: set to vertebrata
    species: 1,
    query: 'Some query',
    max_prots: 650,
    blast: {
      enabled: false,
      evalue: '1e-5',
      seqident: 80,
      qcov: 80
    },
    auto_select: true,
    multi_ortho_selection: null
  },
  output: {
    rid: '',
    unknown_proteins: [],
    multi_ortho: [],
    progress_prottable: defaultPB,
    progress_heatmap: defaultPB,
    prot_table_data: [],
    missing_uniprot: [],
    corr_map_ver: '',
    corr_table: [],
    progress_tree: defaultPB,
    tree: {
      version: '',
      blasted: 0
    }
  }
}