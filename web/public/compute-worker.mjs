import {correlate} from './model.mjs';
self.onmessage = ({data}) => {
  try {const started=performance.now();const result=correlate(data.dataset);self.postMessage({...result,milliseconds:performance.now()-started},result.packedMatrix?[result.packedMatrix.buffer]:[]);}
  catch(error){self.postMessage({error:error.message});}
};
