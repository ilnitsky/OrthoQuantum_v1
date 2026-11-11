import {lossRelatedness} from './loss-score.mjs';
self.onmessage=({data})=>{try{const start=performance.now();self.postMessage({...lossRelatedness(data.dataset,data.options),milliseconds:performance.now()-start});}catch(error){self.postMessage({error:error.message});}};
