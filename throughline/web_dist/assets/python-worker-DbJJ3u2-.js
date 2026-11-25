(function(){let e=`https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`,t=null,n=Promise.resolve(),r=0,i=e=>postMessage(e);function a(){return t??=import(
/* @vite-ignore */
`${e}pyodide.mjs`).then(async({loadPyodide:t})=>{let n=await t({indexURL:e});return n.setStdout({batched:e=>i({id:r,type:`stdout`,text:e+`
`})}),n.setStderr({batched:e=>i({id:r,type:`stderr`,text:e+`
`})}),n.setStdin({error:!0}),n}),t.catch(()=>t=null),t}function o(e){let t=e.split(`
`),n=t.findIndex(e=>e.includes(`File "<exec>"`));return(n>0?[t[0],...t.slice(n)]:t).join(`
`).trim()}async function s({id:e,code:t}){r=e;let n;try{i({id:e,type:`loading`}),n=await a()}catch(t){i({id:e,type:`error`,text:String(t?.message??t),load:!0});return}try{i({id:e,type:`running`}),await n.loadPackagesFromImports(t,{messageCallback:()=>{}});let r=await n.runPythonAsync(t,{globals:n.globals.get(`dict`)()}),a=r==null?null:String(r.toString());r?.destroy?.(),i({id:e,type:`done`,result:a})}catch(t){i({id:e,type:`error`,text:o(String(t?.message??t))})}}onmessage=e=>{n=n.then(()=>s(e.data))}})();