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
from telethon.tl.types import InputPeerChat, InputPeerUser, Message, MessageReplyHeader



# App Configurations #
#---------------------------------------------------------------------------------
load_dotenv(find_dotenv())
phone = getenv("PHONE", None)
api_id = getenv("API_ID", None)
api_hash = getenv("API_HASH", None)

message_copy_dict: dict = None
SOURCE_ID = getenv("SOURCE", None)
DEST_ID = getenv("DESTINATION", None)

message_has_been_sent = asyncio.Event()
ALLOWED_MESSAGE_TYPES= [
    MessageReplyHeader,
    Message
]
send_message_result = None
link_copied_message_id = {}




# App methods #
#--------------------------------------------------------------------------


#Main function
async def main():

    src_chat_id = SOURCE_ID
    dst_chat_id = DEST_ID

    try:
        with open("data/message_copy_dict.pickle", "rb") as f:
            message_copy_dict = pickle.load(f)
    except OSError:
        message_copy_dict = dict()

    async with TelegramClient(phone, api_id, api_hash) as tg :

        #Start Client
        await tg.start(phone)

        #get dialogs(chats)
        dialogs = await tg.get_dialogs()

        # Print information about each chat
        for dialog in dialogs:
            print(f'Chat ID: {dialog.id}, Chat Name: {dialog.name}')

        chat_ids = [dialog.id for dialog in dialogs]

        if (not src_chat_id or not dst_chat_id):
            print("\nPlease enter SOURCE and DESTINATION in .env file")
            exit(1)
        else:
            src_chat_id = int(src_chat_id)
            dst_chat_id = int(dst_chat_id)

        src_entity =await tg.get_entity(src_chat_id)
        dst_entity =await tg.get_entity(dst_chat_id)
        print(f'Retrieved Entities: \nSource-->{src_entity.title} \n Destination --> {dst_entity.title}\n')

        #Fetch ids from source and Destination
        print(f"Fetching messages from src_chat {src_entity.title}...")
        collector_for_all_message_ids_in_src_chat = await collect_messages(tg,src_chat_id)
        print(f"Got a total of {len(collector_for_all_message_ids_in_src_chat)} messages from source chat")

        print()
        print(f"Fetching messages from dst_chat_id {dst_entity.title}...")
        collector_for_all_message_ids_in_dst_chat_id =await collect_messages(tg, dst_chat_id)


        print("Processing...")
        grouped_media_caption: str=None
        grouped_messages=[]
        group_id: int = None
        for message_id in reversed(collector_for_all_message_ids_in_src_chat): #the last message or first message when reversed prints out channel name!
            # try:
            message = await tg.get_messages(src_chat_id, ids=message_id)

            # Check if the message is of type Message and not MessageService
            # if not isinstance(message, Message):
            if type(message) not in  ALLOWED_MESSAGE_TYPES:
                print(f"Fetched message is a {type(message)} instead of one of these: \n{ALLOWED_MESSAGE_TYPES}")
                print(f"\n {message} \n sourceID {src_chat_id}")
                continue

                if isinstance(message, MessageReplyHeader):
                    print(message)

            #send message if not part of a grouped media
            if message.message != "" and message.media is not None:
                grouped_media_caption=message.message

            # if text message sent after a grouped media message is created, send media before the text message
            if message.grouped_id is None:
                if grouped_messages:
                    await tg.send_file(dst_chat_id, grouped_messages, caption=grouped_media_caption)
                    grouped_messages=[]
                # Send a copy of the message
                send_message_result = await copy_message(tg, dst_entity, message)



            #if message is the first of a group
            elif group_id is None:
                grouped_messages.append(message.media)
                group_id = message.grouped_id
            #if message is part of an existing group
            elif message.grouped_id == group_id:
                grouped_messages.append(message.media)
            #if message is a start of a new group of media
            elif message.grouped_id != group_id:
                print("new group for current message found! ")
                await tg.send_file(dst_chat_id, grouped_messages, caption=grouped_media_caption)
                # refresh setting for a new group of media
                grouped_messages = []
                group_id=[]
                grouped_messages.append(message.media)
                group_id = message.grouped_id
            continue

            # except Exception as e:
            #     print(f"Message causing Error ---> {message}")
            #     print (f"Error ----> {e}")
            #     return None

            # print(f"Sending messages...")
            # continue
        # if a group of media is still exists but is yet to be sent
        if grouped_messages:
            await tg.send_file(dst_chat_id, grouped_messages, caption=grouped_media_caption)


        #return info about destination chat
        r = await tg.get_messages(dst_chat_id, limit=100000)
        new_message_id = r[0].id
        print(f"created link: {message_id} => {new_message_id}")
        message_copy_dict.update({message_id: new_message_id})

        print("...done.")
        print(f"Message Links ----> {link_copied_message_id}")
        makedirs("data",exist_ok=True)
        with open("data/message_copy_dict.pickle", "wb") as f:
            pickle.dump(message_copy_dict, f)


# get messages from chat id
# -----------------------------------
async def collect_messages(tg:TelegramClient, chat_id: int):
    last = 0
    message_ids=[]
    while True:
        print(".",end="",flush=True)
        messages = await tg.get_messages(chat_id, limit=100000, min_id=last)
        if not messages.total:
            break
        for m in messages:
            message_ids.append(m.id)
        last = messages[-1].id
        last_mes = messages[-1]

        print(f"last message:{last} ::: {last_mes.message}")
        print(f'list of messages: {message_ids}')

        if last != 0:
            break
    return message_ids


#Copy function for all message types
# ----------------------------------------------
async def copy_message(tg: TelegramClient, chat_recipient: int, message_obj: Message):
    reply_message = None
    dest_id = DEST_ID

    if message_obj.reply_to:
        reply_id_source = message_obj.reply_to.reply_to_msg_id
        reply_id_dest = link_copied_message_id[f"{reply_id_source}"]
        reply_message = await tg.get_messages(chat_recipient, ids=reply_id_dest)

    sent_message_obj = await tg.send_message(
        chat_recipient,
        message = message_obj.message,
        reply_to=reply_message,
        silent=message_obj.silent,
        file=message_obj.media,  # Assuming 'media' is the media file to send

        # parse_mode=message_obj.parse_mode,
        # reply_markup=message_obj.reply_markup,
        # clear_draft=message_obj.clear_draft,
    )
    # append message ID link from old message to new
    link_copied_message_id[f"{message_obj.id}"] = sent_message_obj.id
    print("Message sent successfully!\n")
    return sent_message_obj





if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    # asyncio.run(main())
