import {correlate} from './model.mjs';
self.onmessage = ({data}) => {
  try {const started=performance.now();const result=correlate(data.dataset);self.postMessage({...result,milliseconds:performance.now()-started});}
  catch(error){self.postMessage({error:error.message});}
};
