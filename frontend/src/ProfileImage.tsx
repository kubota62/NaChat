import { useEffect, useState } from 'react';
import { api, User } from './api';

export function ProfileImage({user,onSaved}:{user:User;onSaved:()=>Promise<void>}){
  const [file,setFile]=useState<File|null>(null),[preview,setPreview]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{if(!file){setPreview('');return}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url)},[file]);
  async function save(remove=false){
    setBusy(true);setError('');
    try{
      if(remove)await api('profile/avatar','DELETE');
      else{const data=new FormData();data.append('avatar',file!);await api('profile/avatar','POST',data)}
      await onSaved();
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <section className="profile-image" aria-label="プロフィール画像">
    <h3>プロフィール画像</h3>
    <div className="profile-image-preview">{preview||user.avatar?<img src={preview||user.avatar!} alt="プロフィール画像のプレビュー"/>:<span>{user.name.slice(0,1)}</span>}</div>
    <label>画像を選択<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={e=>{
      const selected=e.target.files?.[0];setError('');
      if(selected&&selected.size>5*1024*1024){setError('画像は5MB以下にしてください。');setFile(null);e.target.value='';return}
      setFile(selected||null);
    }}/></label>
    <p className="muted">PNG・JPEG・WebP、5MB・2000万画素以下。中央を正方形に切り取り、256×256に縮小します。社内のログインユーザーに表示されます。</p>
    {error&&<p role="alert" className="form-error">{error}</p>}
    <div className="profile-image-buttons"><button className="primary" disabled={!file||busy} onClick={()=>void save()}>{busy?'処理中…':'画像を保存'}</button>{user.avatar&&<button disabled={busy} onClick={()=>void save(true)}>画像を削除</button>}</div>
  </section>;
}
