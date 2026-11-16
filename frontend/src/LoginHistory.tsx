import { useEffect, useRef, useState } from 'react';
import { api } from './api';

type Entry = {id:string;time:string;result:string;account:string;name:string;ip:string;user_agent:string};
type Page = {logs:Entry[];next:string|null};
const labels:Record<string,string> = {success:'成功',failed:'認証失敗',rate_limited:'試行回数制限'};

export function LoginHistory(){
  const [account,setAccount]=useState(''),[result,setResult]=useState('');
  const [page,setPage]=useState<Page>({logs:[],next:null});
  const [filter,setFilter]=useState({account:'',result:''});
  const [busy,setBusy]=useState(true),[error,setError]=useState('');
  const generation=useRef(0);
  async function load(filters:typeof filter,before?:string){
    const current=++generation.current;
    setBusy(true);setError('');
    try{
      const params=new URLSearchParams({...filters,...(before?{before}:{})});
      const data=await api<Page>('login-history?'+params);
      if(current!==generation.current)return;
      setPage(prev=>({logs:before?[...prev.logs,...data.logs]:data.logs,next:data.next}));
      setFilter(filters);
    }catch(e){if(current===generation.current)setError((e as Error).message)}
    finally{if(current===generation.current)setBusy(false)}
  }
  useEffect(()=>{void load({account:'',result:''});return()=>{generation.current++}},[]);
  return <section className="login-history" aria-label="ログイン履歴">
    <p className="muted">新しい順に表示します。日時は日本時間です。</p>
    <form onSubmit={e=>{e.preventDefault();void load({account,result})}}>
      <label>アカウント<input value={account} onChange={e=>setAccount(e.target.value)} maxLength={254} placeholder="メールアドレス・管理者IDの一部"/></label>
      <label>結果<select value={result} onChange={e=>setResult(e.target.value)}><option value="">すべて</option>{Object.entries(labels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <button className="primary" disabled={busy}>絞り込み・更新</button>
    </form>
    {error&&<p role="alert" className="form-error">{error}</p>}
    <p role="status" className="muted">{busy?'読み込み中…':`${page.logs.length}件表示`}</p>
    {!busy&&!error&&page.logs.length===0&&<p className="empty-text">該当するログイン履歴はありません。</p>}
    <div className="login-entries">{page.logs.map(row=><article key={row.id}>
      <header><time dateTime={row.time}>{new Date(row.time).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'})}</time><strong className={'login-result '+row.result}>{labels[row.result]||row.result}</strong></header>
      <dl><dt>アカウント</dt><dd>{row.account||'未入力'}{row.name&&`（${row.name}）`}</dd><dt>接続元IP</dt><dd>{row.ip||'不明'}</dd><dt>ブラウザ情報</dt><dd>{row.user_agent||'不明'}</dd></dl>
    </article>)}</div>
    {page.next&&<button className="load-more" disabled={busy} onClick={()=>void load(filter,page.next!)}>さらに50件表示</button>}
  </section>;
}
