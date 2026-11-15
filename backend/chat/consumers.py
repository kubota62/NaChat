import asyncio
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from .models import User, Room
from .services import can_read

class Updates(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def valid(self,room_id=None):
        key=self.scope['session'].session_key
        s=Session.objects.filter(session_key=key,expire_date__gt=timezone.now()).first()
        if not s: return False
        data=s.get_decoded()
        u=User.objects.filter(pk=data.get('_auth_user_id'),is_active=True,must_change_password=False).first()
        if not u or not constant_time_compare(data.get('_auth_user_hash',''),u.get_session_auth_hash()): return False
        if room_id:
            room=Room.objects.filter(pk=room_id).first()
            return bool(room and can_read(u,room))
        return True
    async def connect(self):
        self.timer=None
        if not await self.valid(): return await self.close(code=4401)
        await self.channel_layer.group_add('updates',self.channel_name)
        await self.accept()
        self.timer=asyncio.create_task(self.watch())
    async def watch(self):
        while True:
            await asyncio.sleep(15)
            if not await self.valid():
                await self.close(code=4401); return
    async def disconnect(self,code):
        if self.timer: self.timer.cancel()
        await self.channel_layer.group_discard('updates',self.channel_name)
    async def room_changed(self,event):
        if await self.valid(event['room_id']): await self.send_json({'room':str(event['room_id']),'version':event['version']})
    async def receive_json(self,content):
        if not await self.valid(): await self.close(code=4401)
