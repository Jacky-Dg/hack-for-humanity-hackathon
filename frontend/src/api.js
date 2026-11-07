const BASE=(import.meta.env.VITE_API_URL||'').replace(/\/$/,'');
export function apiAsset(path){return path?BASE+path:''}
export async function api(path,options={}){
  let r;
  try{r=await fetch(BASE+path,options)}catch{throw Error('Cannot connect to ClearPath server. Check that FastAPI is running.');}
  if(!r.ok){let detail=`Request failed (${r.status})`;try{const data=await r.json();detail=typeof data.detail==='string'?data.detail:detail;}catch{}throw Error(detail)}
  return r.json();
}
