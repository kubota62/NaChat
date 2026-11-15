import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from .models import Room, Message, Change, ThreadRead

def visible_rooms(user):
    return Room.objects.filter(Q(kind='public')|Q(members=user)).distinct()

def can_read(user, room):
    return user.is_active and (room.kind=='public' or room.members.filter(pk=user.pk).exists())

def changed(room, message):
    room.version += 1
    room.save(update_fields=['version','sequence'])
    Change.objects.create(room=room,version=room.version,message=message)
    def send():
        try:
            async_to_sync(get_channel_layer().group_send)('updates',{'type':'room.changed','room_id':room.pk,'version':str(room.version)})
        except Exception:
            logging.getLogger(__name__).exception('Notification failed; periodic synchronization will recover')
    transaction.on_commit(send)

def message_data(message,user):
    reactions={}
    for r in message.reactions.all():
        item=reactions.setdefault(r.emoji,{'emoji':r.emoji,'count':0,'mine':False})
        item['count']+=1
        item['mine'] |= r.user_id==user.pk
    return {'id':str(message.pk),'room':str(message.room_id),'sequence':str(message.sequence),'parent':str(message.parent_id) if message.parent_id else None,'author':{'id':str(message.author_id),'name':message.author.display_name},'body':'' if message.deleted else message.body,'deleted':message.deleted,'created_at':message.created_at.isoformat(),'edited':message.edited_at is not None,'replies':message.replies.count(),'reactions':list(reactions.values()) if not message.deleted else [],'attachments':[{'id':str(a.pk),'name':a.name,'size':a.size} for a in message.attachments.all()] if not message.deleted else []}

def messages():
    return Message.objects.select_related('author').prefetch_related('reactions','attachments')

def unread(room,user):
    member=room.membership_set.filter(user=user).first()
    position=member.read_sequence if member else 0
    pending=Message.objects.filter(room=room,deleted=False).exclude(author=user)
    total=pending.filter(parent=None,sequence__gt=position).count()
    reads=dict(ThreadRead.objects.filter(user=user,parent__room=room).values_list('parent_id','sequence'))
    total+=sum(1 for parent,seq in pending.exclude(parent=None).values_list('parent_id','sequence') if seq>reads.get(parent,0))
    return total
