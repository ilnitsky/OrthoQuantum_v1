import type { Binary, ObjectId, WithId } from 'mongodb';

// generic
export type Data = {
	/** valtio proxy with user input (combines server data with user's modifications) */
	input: object;
	/** valtio proxy with results from server */
	output: object;
};
export type TimestampedData<T extends Data> = [data: T, ts: string];

export const HIDDEN = 0;
export const QUEUE = 1;
export const ERROR = 2;
export const PROGRESS = 3;

export type DBTaxon = {
	name: string;
	priority: number;
	species: {
		name: string;
		taxid: number;
	}[];
};

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

export type Input = {
	taxon_id?: string;
	species?: number;
	query: string;
	max_prots: number;
	blast: {
		enabled: boolean;
		evalue: string;
		/**
		 * @minimum 0
		 * @maximum 100
		 */
		pident: number;
		/**
		 * @minimum 0
		 * @maximum 100
		 */
		qcov: number;
	};
	auto_select: boolean;
	multi_ortho_selection: MultiOrthoID[];
};

export type SubmitQuery = Pick<DBQuery, 'title' | 'input'>;

export type MultiOrtho = [
	id: string,
	query: string,
	orthodb_id: string,
	gene_name: string,
	description: string,
	gene_count: string,
	species_count: string
];
export type MultiOrthoID = MultiOrtho[0];

export type Output = {
	/** Run id */
	rid?: string;
	unknown_proteins?: string[];
	multi_ortho?: MultiOrtho[];
	progress_prottable?: ProgressBar;
	progress_heatmap?: ProgressBar;
	prot_table_data?: string[][];
	missing_uniprot?: string[];
	/** png image of correlation */
	corr_map_ver?: string;
	corr_table?: {
		a: string;
		b: string;
		/** correlation */
		c: number;
		/** quantile */
		q: number;
	}[];
	progress_tree?: ProgressBar;
	tree?: {
		version: string;
		blasted: number;
	};
};

export type DBQuery = {
	uid: ObjectId;
	_id: Binary;
	title: string;
	input: Input;
	output: Output;
	last_submit: Date;
	last_view: Date;
};
export type Query = Pick<DBQuery, 'title' | 'input' | 'output'>;

export type DBUser = {
	showTutorial: boolean;
	tokens: {
		token: Binary;
		expires?: Date;
	}[];
};

export type User = WithId<Omit<DBUser, 'tokens'>>;
