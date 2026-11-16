export type User={id:string;name:string;avatar:string|null;email:string;admin:boolean;must_change_password:boolean;active:boolean};
export type Room={id:string;name:string;kind:string;description:string;owner:string;version:string;unread:number;members:string[]};
export type Message={id:string;room:string;sequence:string;parent:string|null;author:{id:string;name:string;avatar:string|null};body:string;deleted:boolean;created_at:string;edited:boolean;replies:number;reactions:{emoji:string;count:number;mine:boolean}[];attachments:{id:string;name:string;size:number}[]};
let csrf='';
export async function api<T=any>(path:string,method='GET',data?:unknown):Promise<T>{
  if(method!=='GET'&&!csrf){const r=await fetch('/api/csrf');csrf=(await r.json()).csrf;}
  const form=data instanceof FormData;
  const r=await fetch('/api/'+path,{method,credentials:'same-origin',headers:{...(method!=='GET'?{'X-CSRFToken':csrf}:{}),...(!form&&data?{'Content-Type':'application/json'}:{})},body:data?(form?data:JSON.stringify(data)):undefined});
  const result=await r.json().catch(()=>({error:'通信に失敗しました。'}));
  if(r.status===401&&path!=='login')window.dispatchEvent(new Event('nachat:signout'));
  if(!r.ok)throw new Error(result.error||'処理に失敗しました。');
  if(['login','logout','password'].includes(path))csrf='';
  return result;
}
export function subscribe(onChange:()=>void,onStatus:(status:boolean)=>void){
  let socket:WebSocket;let stopped=false;let timer:ReturnType<typeof setTimeout>;
  const connect=()=>{socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);socket.onopen=()=>{onStatus(true);onChange()};socket.onmessage=onChange;socket.onclose=()=>{onStatus(false);if(!stopped)timer=setTimeout(connect,3000)};socket.onerror=()=>socket.close()};
  connect();return()=>{stopped=true;clearTimeout(timer);socket.close()};
}
