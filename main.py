# MIT License
#
# Copyright (c) 2023 Robert Giessmann
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from os import getenv, makedirs
import pickle
from sys import exit
from telethon.sessions.sqlite import PeerChannel, PeerChat
from telethon.tl.custom import dialog, message
import threading
import asyncio

from dotenv import load_dotenv, find_dotenv
from telethon.sync import TelegramClient, events
from telethon.tl.types import InputPeerChat, InputPeerUser, Message, MessageReplyHeader, MessageMediaDocument, User, Channel, MessageMediaWebPage



# Environment Variables Configuration #
#---------------------------------------------------------------------------------
load_dotenv(find_dotenv())
phone = getenv("PHONE", None)
api_id = getenv("API_ID", None)
api_hash = getenv("API_HASH", None)
#Source and destination config
SOURCE_ID = getenv("SOURCE", None)
DEST_ID = getenv("DESTINATION", None)

# Literals and Global Configuration
link_copied_message_id = {}
message_copy_dict: dict = None
ALLOWED_MESSAGE_TYPES= [
    MessageReplyHeader,
    Message
]




# Functions #
#--------------------------------------------------------------------------

#Main function
async def main():

    src_chat_id = SOURCE_ID
    dst_chat_id = DEST_ID

    ## Keeping track of previous or already sent messages
    # try:
    #     with open("data/message_copy_dict.pickle", "rb") as f:
    #         message_copy_dict = pickle.load(f)
    # except OSError:
    #     message_copy_dict = dict()

    async with TelegramClient(phone, api_id, api_hash) as tg :

        #Start Client
        await tg.start(phone)

        #get chats
        dialogs = await tg.get_dialogs()

        # Print information about each chat
        for dialog in dialogs:
            print(f'Chat ID: {dialog.id}, Chat Name: {dialog.name}')

        # Gather chat IDs
        chat_ids = [dialog.id for dialog in dialogs]

        if (not src_chat_id or not dst_chat_id):
            print("\nPlease enter SOURCE and DESTINATION in .env file")
            exit(1)
        else:
            src_chat_id = int(src_chat_id)
            dst_chat_id = int(dst_chat_id)

        #Get Source and Destination Chat entity
        src_entity =await tg.get_entity(src_chat_id)
        dst_entity =await tg.get_entity(dst_chat_id)
        src_title = get_title(src_entity)
        dst_title = get_title(dst_entity)
        print(f'Retrieved Entities: \nSource-->{src_title} \n Destination --> {dst_title}\n')

        #Fetch ids from source and Destination
        print(f"Fetching messages from src_chat {src_title}...")
        collector_for_all_message_ids_in_src_chat = await collect_messages(tg, src_chat_id)
        print(f"Got a total of {len(collector_for_all_message_ids_in_src_chat)} messages from source chat")

        print()
        print(f"Fetching messages from dst_chat_id {dst_title}...")
        collector_for_all_message_ids_in_dst_chat_id =await collect_messages(tg, dst_chat_id)


        print("Processing...")
        # Holds previous message after a new iteration starts
        # and the iteration does not fit in a group of media or is and new group of media.
        # sendin
        previous_message: Message = None #holds info about previous iteration to
        grouped_media_caption: str=None
        grouped_media: list=[]
        group_id: int = None  #Identifies the group id of a media message (2 messages with identical group ids are in the same group)

        # Iterates through collected messages in source chat
        for message_id in reversed(collector_for_all_message_ids_in_src_chat): #the last message or first message when reversed prints out channel name!
            message = await tg.get_messages(src_chat_id, ids=message_id)

            # Check if the message is of type Message and not MessageService
            if type(message) not in ALLOWED_MESSAGE_TYPES:
                print()
                print(f"Error: Fetched message is a {type(message)} instead of one of these: \n{ALLOWED_MESSAGE_TYPES}")
                print()
                print(f"message raising error: --> \n{message}")
                print()
                continue


            # Store to previous message and add caption if message is a MEDIA with a CAPTION
            if message.message != "" and message.media is not None:
                grouped_media_caption=message.message
                previous_message = message

            # If new iteration(media message) is not part of a group of media (initiated previously),
            # after a grouped media has be initiated or created,
            # Send media(previously set as previous message) before sending current iteration(media)
            if message.grouped_id is None: # If message is not a grouped message(media)
                if grouped_media: # If a group of media messages is initiated but not sent/handled
                    sent_file = await tg.send_file(dst_chat_id, grouped_media, caption=grouped_media_caption)
                    link_copied_message_id[f"{previous_message.id}"] = sent_file[-1].id
                    grouped_media=[]
                # Send a copy of the message
                await copy_message(tg, dst_entity, message)



            #assign a new group id if group id is empty
            elif group_id is None:
                grouped_media.append(message.media)
                group_id = message.grouped_id
                previous_message = message
            #if message is part of the existing group
            elif message.grouped_id == group_id:
                grouped_media.append(message.media)
                previous_message = message
            # if message media is not a part of an existing group of media,
            # Send the existing group of media
            # create a new group of media.
            elif message.grouped_id != group_id:
                print("new group for current message found! ")
                sent_file=await tg.send_file(dst_chat_id, grouped_media, caption=grouped_media_caption) #send existing group media
                link_copied_message_id[f"{previous_message.id}"] = sent_file[-1].id
                # refresh lists for a new group of media and new group id
                grouped_media = []
                group_id=[]
                # new group configuration
                grouped_media.append(message.media)
                group_id = message.grouped_id
            continue

        # # if a group of media is still exists but is yet to be sent
        # if grouped_media:
        #     await tg.send_file(dst_chat_id, grouped_media, caption=grouped_media_caption)


        # Linking source messages and destination messages id to prevent duplication
        # r = await tg.get_messages(dst_chat_id, limit=100000)
        # new_message_id = r[0].id
        # print(f"created link: {message_id} => {new_message_id}")
        # message_copy_dict.update({message_id: new_message_id})

        print("...done.")
        print(f"Source to Destination Message ID Links ----> {link_copied_message_id}")
        # makedirs("data",exist_ok=True)
        # with open("data/message_copy_dict.pickle", "wb") as f:
        #     pickle.dump(message_copy_dict, f)


# get messages from chat id
# -----------------------------------
async def collect_messages(tg:TelegramClient, chat_id: int):
    try:
        message_ids=[]
        # while True:
        print(".",end="",flush=True)
        messages = await tg.get_messages(chat_id, limit=100000)
        if not messages.total:
            print("Chat is Empty!")
            return message_ids
        for m in messages:
            message_ids.append(m.id)

        print(f'list of retrieved message IDs: {message_ids}')
    except Exception as e:
        print(f"Error Occured in collect_messages function --> {e} ")
        return None
    return message_ids


#Copy function for all message types
# ----------------------------------------------
async def copy_message(tg: TelegramClient, chat_recipient: int, message_obj: Message):
    reply_message:Message = None #Holds message being replied to!
    dest_id = DEST_ID
    link_preview:bool = False

    # if message is a reply to another message
    if message_obj.reply_to:
        try:
            reply_id_source = message_obj.reply_to.reply_to_msg_id
            reply_id_dest = link_copied_message_id[f"{reply_id_source}"]
            reply_message = await tg.get_messages(chat_recipient, ids=reply_id_dest)
        except Exception as e:
            print()
            print(f"Error in copy_message function----> {e}")
            print(message_obj)

    if isinstance(message_obj.media, MessageMediaWebPage):
        message_obj.media = None
        link_preview = True

    try:
        sent_message_obj = await tg.send_message(
            chat_recipient,
            message = message_obj.message,
            reply_to=reply_message,
            silent=message_obj.silent,
            file=message_obj.media,  # Assuming 'media' is the media file to send
            link_preview = link_preview
            # parse_mode=message_obj.parse_mode,
            # reply_markup=message_obj.reply_markup,
            # clear_draft=message_obj.clear_draft,
        )
    except Exception as e:
        print()
        print(message_obj)
        print(f"Error found while Sending message ----> {e}")

    # append message ID link from old message to new
    link_copied_message_id[f"{message_obj.id}"] = sent_message_obj.id
    print(f"Message of ID ->{message_obj.id} sent successfully!")
    return sent_message_obj

def get_title(entity):
    if type(entity) == User:
        return entity.first_name
    elif type(entity) == Channel:
        return entity.title






if __name__ == "__main__":
    asyncio.run(main())
