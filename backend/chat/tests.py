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
    def test_first_password_gate_and_session_revocation(self):
        self.a.must_change_password=True;self.a.save()
        self.assertEqual(self.client.get('/api/rooms').status_code,403)
        r=self.post('password',{'current':'Testing!Password12','password':'Different!Password34'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/rooms').status_code,200)
        self.a.refresh_from_db();self.a.set_password('Reset!Password56');self.a.save()
        self.assertEqual(self.client.get('/api/rooms').status_code,401)
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
