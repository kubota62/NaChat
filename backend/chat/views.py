import json, uuid, hashlib, io
from functools import wraps
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from django.utils import timezone
from .models import User, Room, Membership, Message, ThreadRead, Reaction, Change, Attachment, Audit
from .services import visible_rooms, can_read, changed, message_data, messages, unread

def api(methods, public=False):
    def wrap(fn):
        @wraps(fn)
        def run(request,*args,**kwargs):
            if request.method not in methods: return JsonResponse({'error':'Method not allowed'},status=405)
            if not public and not request.user.is_authenticated: return JsonResponse({'error':'ログインしてください。'},status=401)
            try:
                request.payload=json.loads(request.body or b'{}') if request.content_type=='application/json' else request.POST.dict()
                if not isinstance(request.payload,dict): raise ValueError()
                return fn(request,*args,**kwargs)
            except (ValueError,TypeError,ValidationError) as e:
                return JsonResponse({'error':' / '.join(e.messages) if isinstance(e,ValidationError) else '入力内容を確認してください。'},status=400)
        return run
    return wrap

def user_data(u): return {'id':str(u.pk),'name':u.display_name,'email':u.email,'admin':u.is_staff,'must_change_password':u.must_change_password,'active':u.is_active}
def require_room(request,pk,lock=False):
    room=get_object_or_404(Room.objects.select_for_update() if lock else Room.objects,pk=pk)
    if not can_read(request.user,room): raise Http404()
    return room
def room_data(room,u):
    name=room.name
    if room.kind=='dm': name=', '.join(room.members.exclude(pk=u.pk).values_list('display_name',flat=True))
    return {'id':str(room.pk),'name':name,'description':room.description,'kind':room.kind,'owner':str(room.owner_id),'version':str(room.version),'unread':unread(room,u),'members':[str(x) for x in room.members.values_list('id',flat=True)]}

@api(['GET'],public=True)
def csrf(request): return JsonResponse({'csrf':get_token(request)})
@api(['GET'],public=True)
def health(request): return JsonResponse({'status':'ok'})
@api(['POST'],public=True)
def sign_in(request):
    email=str(request.payload.get('email','')).strip().lower()
    key='login:'+hashlib.sha256((request.META.get('REMOTE_ADDR','')+email).encode()).hexdigest()
    if cache.get(key,0)>=10: return JsonResponse({'error':'試行回数の上限です。15分後にお試しください。'},status=429)
    cache.add(key,0,900)
    cache.incr(key)
    u=authenticate(request,username=email,password=request.payload.get('password',''))
    if not u: return JsonResponse({'error':'メールアドレスまたはパスワードが違います。'},status=401)
    cache.delete(key)
    login(request,u)
    return JsonResponse(user_data(u))
@api(['POST'])
def sign_out(request):
    logout(request)
    return JsonResponse({'ok':True})
@api(['GET'])
def me(request): return JsonResponse(user_data(request.user))
@api(['POST'])
def password(request):
    if not request.user.check_password(request.payload.get('current','')): return JsonResponse({'error':'現在のパスワードが違います。'},status=400)
    new=request.payload.get('password','')
    validate_password(new,request.user)
    if request.user.check_password(new): raise ValidationError('新しいパスワードを指定してください。')
    request.user.set_password(new)
    request.user.must_change_password=False
    request.user.save()
    update_session_auth_hash(request,request.user)
    Audit.objects.create(actor=request.user,action='password_changed',target=str(request.user.pk))
    return JsonResponse(user_data(request.user))

@api(['GET','POST'])
def users(request):
    if request.method=='GET':
        qs=User.objects.all() if request.user.is_staff else User.objects.filter(is_active=True)
        return JsonResponse({'users':[user_data(u) for u in qs.order_by('display_name')]})
    if not request.user.is_staff: return JsonResponse({'error':'管理者のみ操作できます。'},status=403)
    data=request.payload
    email=str(data.get('email','')).strip().lower()
    validate_email(email)
    if User.objects.filter(email=email).exists(): raise ValidationError('登録済みのメールアドレスです。')
    name=str(data.get('name','')).strip()
    if not name or len(name)>80: raise ValueError()
    u=User(email=email,display_name=name)
    validate_password(data.get('password',''),u)
    u.set_password(data['password']); u.save()
    Audit.objects.create(actor=request.user,action='user_created',target=str(u.pk))
    return JsonResponse(user_data(u),status=201)

@api(['POST'])
def manage_user(request,pk):
    if not request.user.is_staff: return JsonResponse({'error':'管理者のみ操作できます。'},status=403)
    u=get_object_or_404(User,pk=pk)
    if u.is_superuser: raise ValidationError('最上位管理者の変更はホスト上の管理コマンドを使用してください。')
    if 'active' in request.payload: u.is_active=bool(request.payload['active'])
    if request.payload.get('password'):
        validate_password(request.payload['password'],u)
        u.set_password(request.payload['password']); u.must_change_password=True
    u.save()
    Audit.objects.create(actor=request.user,action='user_updated',target=str(u.pk))
    return JsonResponse(user_data(u))

@api(['GET','POST'])
def rooms(request):
    if request.method=='GET': return JsonResponse({'rooms':[room_data(r,request.user) for r in visible_rooms(request.user).order_by('kind','name')]})
    data=request.payload
    kind=data.get('kind','public')
    if kind not in ['public','private','dm']: raise ValueError()
    with transaction.atomic():
        if kind=='dm':
            other=get_object_or_404(User,pk=data.get('user'),is_active=True)
            if other.pk==request.user.pk: raise ValueError()
            key=':'.join(map(str,sorted([other.pk,request.user.pk])))
            room,_=Room.objects.get_or_create(dm_key=key,defaults={'name':'DM','kind':'dm','owner':request.user})
            Membership.objects.get_or_create(room=room,user=other)
        else:
            name=str(data.get('name','')).strip()
            if not name or len(name)>80: raise ValueError()
            room=Room.objects.create(name=name,description=str(data.get('description',''))[:300],kind=kind,owner=request.user)
        Membership.objects.get_or_create(room=room,user=request.user)
    return JsonResponse(room_data(room,request.user),status=201)

@api(['POST','DELETE'])
def members(request,pk):
    with transaction.atomic():
        room=require_room(request,pk,True)
        if room.kind=='dm' or room.owner_id!=request.user.pk: return JsonResponse({'error':'チャンネル作成者のみ変更できます。'},status=403)
        u=get_object_or_404(User,pk=request.payload.get('user'),is_active=True)
        if request.method=='POST': Membership.objects.get_or_create(room=room,user=u)
        else:
            if u.pk==room.owner_id: raise ValidationError('作成者は削除できません。')
            Membership.objects.filter(room=room,user=u).delete()
        Audit.objects.create(actor=request.user,action='membership_'+request.method.lower(),target=f'{room.pk}:{u.pk}')
    return JsonResponse({'ok':True})

@api(['GET','POST'])
def room_messages(request,pk):
    if request.method=='GET':
        room=require_room(request,pk)
        parent=request.GET.get('parent')
        qs=messages().filter(room=room,parent_id=parent or None)
        before=request.GET.get('before')
        if before: qs=qs.filter(sequence__lt=int(before))
        batch=list(qs.order_by('-sequence')[:51]); more=len(batch)>50
        return JsonResponse({'messages':[message_data(m,request.user) for m in reversed(batch[:50])],'more':more})
    with transaction.atomic():
        room=require_room(request,pk,True)
        data=request.payload
        client_id=uuid.UUID(data.get('client_id',''))
        old=Message.objects.filter(author=request.user,client_id=client_id).first()
        if old:
            if old.room_id!=room.pk: raise ValidationError('投稿IDが重複しています。')
            return JsonResponse(message_data(old,request.user))
        body=str(data.get('body','')).strip()
        uploads=request.FILES.getlist('files')
        if len(body)>10000 or (not body and not uploads) or len(uploads)>5: raise ValueError()
        if sum(f.size for f in uploads)>25*1024*1024: raise ValidationError('添付は合計25MBまでです。')
        parent=None
        if data.get('parent'): parent=get_object_or_404(Message,pk=data['parent'],room=room,parent=None,deleted=False)
        room.sequence+=1
        m=Message.objects.create(room=room,author=request.user,client_id=client_id,sequence=room.sequence,body=body,parent=parent)
        for f in uploads: Attachment.objects.create(message=m,name=f.name[:255],file=f,size=f.size)
        changed(room,m)
    return JsonResponse(message_data(m,request.user),status=201)

@api(['GET'])
def changes(request,pk):
    room=require_room(request,pk)
    after=max(0,int(request.GET.get('after','0')))
    batch=list(Change.objects.filter(room=room,version__gt=after).order_by('version')[:200])
    return JsonResponse({'changes':[{'version':str(c.version),'message':message_data(messages().get(pk=c.message_id),request.user)} for c in batch],'cursor':str(batch[-1].version if batch else after),'latest':str(max(room.version,batch[-1].version if batch else 0))})

@api(['GET','PATCH','DELETE'])
def message(request,pk):
    if request.method=='GET':
        m=get_object_or_404(messages(),pk=pk)
        require_room(request,m.room_id)
        return JsonResponse(message_data(m,request.user))
    with transaction.atomic():
        m=get_object_or_404(Message,pk=pk)
        room=require_room(request,m.room_id,True)
        m=Message.objects.get(pk=pk)
        if m.author_id!=request.user.pk: return JsonResponse({'error':'自分の投稿のみ変更できます。'},status=403)
        if m.deleted: raise ValidationError('削除済みです。')
        if request.method=='DELETE': m.deleted=True; m.body=''
        else:
            body=str(request.payload.get('body','')).strip()
            if not body or len(body)>10000: raise ValueError()
            m.body=body; m.edited_at=timezone.now()
        m.save(); changed(room,m)
    return JsonResponse(message_data(m,request.user))

@api(['POST'])
def reaction(request,pk):
    with transaction.atomic():
        m=get_object_or_404(Message,pk=pk)
        room=require_room(request,m.room_id,True)
        m=Message.objects.get(pk=pk)
        emoji=request.payload.get('emoji')
        if m.deleted or emoji not in ['👍','❤️','🎉','👀','✅']: raise ValueError()
        r,created=Reaction.objects.get_or_create(message=m,user=request.user,emoji=emoji)
        if not created: r.delete()
        changed(room,m)
    return JsonResponse(message_data(m,request.user))

@api(['POST'])
def read(request,pk):
    with transaction.atomic():
        room=require_room(request,pk,True)
        seq=min(max(0,int(request.payload.get('sequence','0'))),room.sequence)
        parent=request.payload.get('parent')
        if parent:
            p=get_object_or_404(Message,pk=parent,room=room,parent=None)
            marker,_=ThreadRead.objects.get_or_create(parent=p,user=request.user)
            marker.sequence=max(marker.sequence,seq); marker.save()
        else:
            marker,_=Membership.objects.get_or_create(room=room,user=request.user)
            marker.read_sequence=max(marker.read_sequence,seq); marker.save()
    return JsonResponse({'ok':True})

@api(['GET'])
def search(request):
    q=request.GET.get('q','').strip()[:100]
    if not q: return JsonResponse({'messages':[]})
    qs=messages().filter(room__in=visible_rooms(request.user),deleted=False,body__icontains=q)
    return JsonResponse({'messages':[message_data(m,request.user) for m in qs.order_by('-created_at')[:50]]})

@api(['GET'])
def attachment(request,pk):
    a=get_object_or_404(Attachment.objects.select_related('message__room'),pk=pk,message__deleted=False)
    if not can_read(request.user,a.message.room): raise Http404()
    if request.GET.get('preview')=='1':
        from PIL import Image, UnidentifiedImageError
        try:
            with a.file.open('rb') as source, Image.open(source) as img:
                if img.format not in ['PNG','JPEG','WEBP'] or img.width*img.height>20_000_000: raise Http404()
                img.thumbnail((960,720))
                out=io.BytesIO();img.convert('RGB').save(out,format='JPEG',quality=85);out.seek(0)
            response=FileResponse(out,content_type='image/jpeg')
            response['X-Content-Type-Options']='nosniff'
            response['Cache-Control']='private, no-store'
            return response
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError): raise Http404()
    response=FileResponse(a.file.open('rb'),as_attachment=True,filename=a.name,content_type='application/octet-stream')
    response['Content-Security-Policy']="default-src 'none'; sandbox"
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store'
    return response
