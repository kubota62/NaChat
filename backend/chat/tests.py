import json,uuid,tempfile,io
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from .models import User, Room, Membership, Message, Change, ThreadRead

class ChatTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media=tempfile.TemporaryDirectory()
        cls.override=override_settings(MEDIA_ROOT=cls.media.name)
        cls.override.enable()
        cls.addClassCleanup(cls.media.cleanup)
        cls.addClassCleanup(cls.override.disable)
    def setUp(self):
        cache.clear()
        self.a=User.objects.create_user('a@example.test','Testing!Password12',display_name='Alice',must_change_password=False)
        self.b=User.objects.create_user('b@example.test','Testing!Password12',display_name='Bob',must_change_password=False)
        self.room=Room.objects.create(name='private',kind='private',owner=self.a)
        Membership.objects.create(room=self.room,user=self.a)
        self.client.force_login(self.a)
    def post(self,url,data):return self.client.post('/api/'+url,json.dumps(data),content_type='application/json')
    def message(self,body='hello',**extra):
        return self.post(f'rooms/{self.room.pk}/messages',{'body':body,'client_id':str(uuid.uuid4()),**extra})
    def test_private_history_search_attachment_changes_hidden(self):
        r=self.client.post(f'/api/rooms/{self.room.pk}/messages',{'body':'secret','client_id':str(uuid.uuid4()),'files':SimpleUploadedFile('danger.html',b'<script>alert(1)</script>')})
        self.assertEqual(r.status_code,201)
        aid=r.json()['attachments'][0]['id']
        response=self.client.get('/api/attachments/'+aid)
        self.assertIn('attachment',response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.client.force_login(self.b)
        for path in [f'rooms/{self.room.pk}/messages',f'rooms/{self.room.pk}/changes',f'attachments/{aid}']:
            self.assertEqual(self.client.get('/api/'+path).status_code,404)
        self.assertEqual(self.client.get('/api/search?q=secret').json()['messages'],[])
        self.assertEqual(self.message().status_code,404)
    def test_idempotency_and_change_sequence(self):
        cid=str(uuid.uuid4())
        data={'body':'hello','client_id':cid}
        first=self.post(f'rooms/{self.room.pk}/messages',data)
        second=self.post(f'rooms/{self.room.pk}/messages',data)
        self.assertEqual(first.json()['id'],second.json()['id'])
        self.assertEqual(Message.objects.count(),1)
        self.assertEqual(Change.objects.count(),1)
        self.client.patch('/api/messages/'+first.json()['id'],json.dumps({'body':'edited'}),content_type='application/json')
        self.assertEqual(list(Change.objects.values_list('version',flat=True)),[1,2])
    def test_other_author_cannot_edit(self):
        m=self.message().json()
        Membership.objects.create(room=self.room,user=self.b)
        self.client.force_login(self.b)
        self.assertEqual(self.client.delete('/api/messages/'+m['id']).status_code,403)
    def test_optional_password_change_and_session_revocation(self):
        self.a.must_change_password=True;self.a.save()
        self.assertEqual(self.client.get('/api/rooms').status_code,200)
        r=self.post('password',{'current':'Testing!Password12','password':'Different!Password34'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/rooms').status_code,200)
        self.a.refresh_from_db();self.a.set_password('Reset!Password56');self.a.save()
        self.assertEqual(self.client.get('/api/rooms').status_code,401)
    def test_admin_alias_and_eight_character_passwords(self):
        admin=User.objects.create_superuser('admin@nachat.local','administorator',display_name='管理者')
        self.client.logout()
        self.assertEqual(self.post('login',{'email':'administorator','password':'incorrect'}).status_code,401)
        r=self.post('login',{'email':'administorator','password':'administorator'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['name'],'管理者')
        self.assertFalse(r.json()['must_change_password'])
        self.assertEqual(self.client.get('/api/rooms').status_code,200)
        data={'email':'new@example.test','name':'New','password':'Q7!zR2@'}
        self.assertEqual(self.post('users',data).status_code,400)
        data['password']='Q7!zR2@x'
        r=self.post('users',data)
        self.assertEqual(r.status_code,201)
        self.assertFalse(r.json()['must_change_password'])
        uid=r.json()['id']
        self.assertEqual(self.post('users/'+uid,{'password':'T8!vS3#'}).status_code,400)
        self.assertFalse(self.post('users/'+uid,{'password':'T8!vS3#y'}).json()['must_change_password'])
        self.client.logout()
        self.assertEqual(self.post('login',{'email':data['email'],'password':'T8!vS3#y'}).status_code,200)
        self.assertEqual(self.client.get('/api/rooms').status_code,200)
        self.assertEqual(self.post('password',{'current':'T8!vS3#y','password':'V9@kL4!'}).status_code,400)
        self.assertEqual(self.post('password',{'current':'T8!vS3#y','password':'V9@kL4!n'}).status_code,200)

    def test_login_audit_success_failure_limit_and_no_secrets(self):
        from .models import Audit
        from django.core.management import call_command
        self.client.logout()
        headers={'HTTP_X_REAL_IP':'192.168.2.42','HTTP_X_FORWARDED_FOR':'203.0.113.99','HTTP_USER_AGENT':'Firefox test'}
        def attempt(password):
            return self.client.post('/api/login',json.dumps({'email':self.a.email,'password':password}),content_type='application/json',**headers)
        self.assertEqual(attempt('Testing!Password12').status_code,200)
        row=Audit.objects.get(action='login_success')
        self.assertEqual(row.actor_id,self.a.pk)
        self.assertEqual(row.details['ip'],'192.168.2.42')
        self.assertEqual(row.details['user_agent'],'Firefox test')
        self.assertEqual(row.details['display_name'],'Alice')
        self.client.logout()
        for _ in range(10): self.assertEqual(attempt('Wrong!Secret').status_code,401)
        self.assertEqual(attempt('Wrong!Secret').status_code,429)
        self.assertEqual(Audit.objects.filter(action='login_failed',actor=None).count(),10)
        self.assertEqual(Audit.objects.filter(action='login_rate_limited').count(),1)
        out=io.StringIO()
        call_command('login_logs',account=self.a.email,stdout=out)
        lines=out.getvalue().splitlines()
        self.assertEqual(len(lines),12)
        self.assertEqual(json.loads(lines[0])['result'],'rate_limited')
        self.assertNotIn('Wrong!Secret',out.getvalue())
        self.assertNotIn('Testing!Password12',out.getvalue())
        self.assertNotIn('session',out.getvalue())

    def test_login_history_admin_only_filter_and_pagination(self):
        from .models import Audit
        self.client.logout()
        self.assertEqual(self.client.get('/api/login-history').status_code,401)
        self.client.force_login(self.a)
        self.assertEqual(self.client.get('/api/login-history').status_code,403)
        self.a.is_staff=True;self.a.save()
        for i in range(52):
            Audit.objects.create(action='login_success',details={'account':'alice@example.test','ip':'192.168.2.42'})
        Audit.objects.create(action='login_failed',details={'account':'bob@example.test'})
        Audit.objects.create(action='password_changed',details={})
        page=self.client.get('/api/login-history').json()
        self.assertEqual(len(page['logs']),50)
        tail=self.client.get('/api/login-history',{'before':page['next']}).json()
        self.assertEqual(len(tail['logs']),3)
        self.assertIsNone(tail['next'])
        self.assertFalse({r['id'] for r in page['logs']} & {r['id'] for r in tail['logs']})
        filtered=self.client.get('/api/login-history',{'account':'BOB','result':'failed'}).json()
        self.assertEqual(len(filtered['logs']),1)
        self.assertEqual(filtered['logs'][0]['account'],'bob@example.test')
        self.assertEqual(self.client.get('/api/login-history?result=invalid').status_code,400)
        self.assertEqual(self.client.get('/api/login-history?before=invalid').status_code,400)

    def test_profile_image_upload_access_validation_and_delete(self):
        from PIL import Image
        from django.core.files.storage import default_storage
        picture=io.BytesIO();Image.new('RGB',(500,300),'red').save(picture,format='PNG')
        self.assertEqual(self.client.post('/api/profile/avatar',{'avatar':SimpleUploadedFile('x.svg',b'<svg/>')}).status_code,400)
        self.assertEqual(self.client.post('/api/profile/avatar',{'avatar':SimpleUploadedFile('big.png',b'x'*(5*1024*1024+1))}).status_code,400)
        response=self.client.post('/api/profile/avatar',{'avatar':SimpleUploadedFile('profile.png',picture.getvalue()),'user':self.b.pk})
        self.assertEqual(response.status_code,200)
        self.a.refresh_from_db();self.b.refresh_from_db()
        self.assertTrue(self.a.avatar)
        self.assertFalse(self.b.avatar)
        with self.a.avatar.open('rb') as image:
            result=Image.open(image)
            self.assertEqual(result.size,(256,256));self.assertEqual(result.format,'JPEG')
        url=response.json()['avatar']
        self.client.logout();self.assertEqual(self.client.get(url).status_code,401)
        self.client.force_login(self.b)
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\xff\xd8'))
        self.client.force_login(self.a)
        old=self.a.avatar.name
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post('/api/profile/avatar',{'avatar':SimpleUploadedFile('next.png',picture.getvalue())})
        self.assertEqual(response.status_code,200)
        self.assertNotEqual(response.json()['avatar'],url)
        self.assertFalse(default_storage.exists(old))
        self.a.refresh_from_db();old=self.a.avatar.name
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(self.client.delete('/api/profile/avatar').json()['avatar'])
        self.assertFalse(default_storage.exists(old))
        self.assertEqual(self.client.get(url).status_code,404)

    def test_thread_unread_separate_and_never_regresses(self):
        root=self.message().json()
        reply=self.message('reply',parent=root['id']).json()
        Membership.objects.create(room=self.room,user=self.b)
        self.client.force_login(self.b)
        self.post(f'rooms/{self.room.pk}/read',{'sequence':reply['sequence']})
        self.assertEqual(self.client.get('/api/rooms').json()['rooms'][0]['unread'],1)
        self.post(f'rooms/{self.room.pk}/read',{'sequence':reply['sequence'],'parent':root['id']})
        self.post(f'rooms/{self.room.pk}/read',{'sequence':'0','parent':root['id']})
        self.assertEqual(self.client.get('/api/rooms').json()['rooms'][0]['unread'],0)
    def test_cross_room_or_nested_thread_rejected(self):
        root=self.message().json();reply=self.message(parent=root['id']).json()
        self.assertEqual(self.message(parent=reply['id']).status_code,404)
        other=Room.objects.create(name='other',owner=self.a)
        r=self.post(f'rooms/{other.pk}/messages',{'body':'no','client_id':str(uuid.uuid4()),'parent':root['id']})
        self.assertEqual(r.status_code,404)
    def test_dm_unique_and_private(self):
        first=self.post('rooms',{'kind':'dm','user':str(self.b.pk)}).json()
        second=self.post('rooms',{'kind':'dm','user':str(self.b.pk)}).json()
        self.assertEqual(first['id'],second['id'])
        outsider=User.objects.create_user('c@example.test','Password!123456',must_change_password=False)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f"/api/rooms/{first['id']}/messages").status_code,404)
    def test_csrf_enforced(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/login',{'email':self.a.email,'password':'Testing!Password12'}).status_code,403)
    def test_missed_last_notification_recoverable(self):
        with patch('chat.services.get_channel_layer',side_effect=RuntimeError('offline')):
            with self.captureOnCommitCallbacks(execute=True): r=self.message()
        self.assertEqual(r.status_code,201)
        d=self.client.get(f'/api/rooms/{self.room.pk}/changes?after=0').json()
        self.assertEqual(d['cursor'],'1');self.assertEqual(d['changes'][0]['message']['body'],'hello')
    def test_removed_member_loses_access(self):
        Membership.objects.filter(room=self.room,user=self.a).delete()
        self.assertEqual(self.client.get(f'/api/rooms/{self.room.pk}/messages').status_code,404)
    def test_image_preview_reencoded(self):
        from PIL import Image
        data=io.BytesIO();Image.new('RGB',(10,10),'green').save(data,format='PNG')
        r=self.client.post(f'/api/rooms/{self.room.pk}/messages',{'client_id':str(uuid.uuid4()),'files':SimpleUploadedFile('test.png',data.getvalue())})
        self.assertEqual(r.status_code,201)
        aid=r.json()['attachments'][0]['id']
        preview=self.client.get('/api/attachments/'+aid+'?preview=1')
        self.assertEqual(preview.status_code,200)
        self.assertEqual(preview['Content-Type'],'image/jpeg')
        self.assertEqual(preview['Cache-Control'],'private, no-store')

class WebSocketTests(TransactionTestCase):
    def test_origin_and_disabled_user(self):
        from asgiref.sync import async_to_sync
        from asgiref.testing import ApplicationCommunicator
        from channels.db import database_sync_to_async
        from config.asgi import application
        user=User.objects.create_user('ws@example.test','Password!123456',must_change_password=False)
        c=Client();c.force_login(user)
        cookie='sessionid='+c.cookies['sessionid'].value
        async def check():
            def scope(origin): return {'type':'websocket','path':'/ws','headers':[(b'origin',origin),(b'cookie',cookie.encode()),(b'host',b'localhost:8080')],'query_string':b'','subprotocols':[]}
            bad=ApplicationCommunicator(application,scope(b'http://untrusted.example'))
            await bad.send_input({'type':'websocket.connect'})
            self.assertEqual((await bad.receive_output())['type'],'websocket.close')
            await bad.send_input({'type':'websocket.disconnect','code':1000});await bad.wait()
            good=ApplicationCommunicator(application,scope(b'http://localhost:8080'))
            await good.send_input({'type':'websocket.connect'})
            self.assertEqual((await good.receive_output())['type'],'websocket.accept')
            await database_sync_to_async(lambda:User.objects.filter(pk=user.pk).update(is_active=False))()
            await good.send_input({'type':'websocket.receive','text':'{}'})
            self.assertEqual((await good.receive_output())['code'],4401)
            await good.send_input({'type':'websocket.disconnect','code':1000});await good.wait()
        async_to_sync(check)()

class ConcurrentPostTests(TransactionTestCase):
    def test_parallel_posts_and_retries(self):
        user=User.objects.create_user('parallel@example.test','Password!123456',must_change_password=False)
        room=Room.objects.create(name='parallel',owner=user)
        ids=[str(uuid.uuid4()) for _ in range(4)]*2
        def send(cid):
            close_old_connections()
            try:
                c=Client();c.force_login(User.objects.get(pk=user.pk))
                return c.post(f'/api/rooms/{room.pk}/messages',json.dumps({'body':cid,'client_id':cid}),content_type='application/json').status_code
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=4) as pool: statuses=list(pool.map(send,ids))
        self.assertTrue(all(s in [200,201] for s in statuses))
        self.assertEqual(list(Message.objects.order_by('sequence').values_list('sequence',flat=True)),[1,2,3,4])
