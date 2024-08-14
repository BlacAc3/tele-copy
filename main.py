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
from telethon.tl.custom import dialog
import threading
import asyncio

from dotenv import load_dotenv, find_dotenv
from telethon.sync import TelegramClient, events
from telethon.tl.types import InputPeerChat, InputPeerUser, Message



load_dotenv(find_dotenv())

######################
# App Configurations #
######################



phone = getenv("PHONE", None)
api_id = getenv("API_ID", None)
api_hash = getenv("API_HASH", None)

message_has_been_sent = asyncio.Event()
send_message_result = None



EXCLUDE_THESE_MESSAGE_TYPES = [
    "messageChatChangePhoto",
    "messageChatChangeTitle",
    "messageBasicGroupChatCreate",
    "messageChatDeleteMember",
    "messageChatAddMembers",
]

###########################
# Telegram Configurations #
###########################

# tg = Telegram(
#     api_id=getenv("API_ID", None),
#     api_hash=getenv("API_HASH", None),

#     phone=getenv("PHONE", None),

#     database_encryption_key=getenv("DB_PASSWORD"),
#     files_directory=getenv("FILES_DIRECTORY", None),

#     # proxy_server=getenv("PROXY_SERVER"),
#     # proxy_port=getenv("PROXY_PORT"),
#     # proxy_type={
#     #       # 'proxyTypeSocks5', 'proxyTypeMtproto', 'proxyTypeHttp'
#     #       '@type': getenv("PROXY_TYPE"),
#     # },
# )



###############
# App methods #
###############


async def copy_message(tg: TelegramClient, chat_recipient: int, message_obj: Message):
    sent_message_obj = await tg.send_message(
        chat_recipient,
        message = message_obj.message,
        reply_to=message_obj.reply_to,
        silent=message_obj.silent,
        file=message_obj.media,  # Assuming 'media' is the media file to send
        grouped_id=message_obj.grouped_id,

        # parse_mode=message_obj.parse_mode,
        # reply_markup=message_obj.reply_markup,
        # clear_draft=message_obj.clear_draft,
        buttons=message_obj.buttons,  # Assuming 'buttons' are the inline keyboard buttons
    )
    print("Message sent successfully!\n")
    return sent_message_obj






async def main():
    message_copy_dict: dict = None
    src_chat = getenv("SOURCE", None)
    dst_chat = getenv("DESTINATION", None)


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

        ## Iterate through chats to find specific chats
        # for chat_id in chat_ids:
        #     first_channel_found = False
        #     second_channel_found= False
        #     r = await tg.get_entity(chat_id)

        #     #handle entities type channel or group or chat
        #     try:
        #         title = r.first_name
        #     except:
        #         title = r.title

        #     if title == "Test1 Channel":
        #         first_channel_found = True

        #     if title == "Test2 Channel":
        #         second_channel_found = True
        #     if first_channel_found and second_channel_found:
        #         print(f"{chat_id}, {title}", flush=True)
        #         break
        #     else:
        #         print("Channels not found!!")




        if (not src_chat or not dst_chat):
            print("\nPlease enter SOURCE and DESTINATION in .env file")
            exit(1)
        else:
            src_chat = int(src_chat)
            dst_chat = int(dst_chat)

        src_entity =await tg.get_entity(src_chat)
        dst_entity =await tg.get_entity(dst_chat)
        print(f'Retrieved Entities: \nSource-->{src_entity.title} \n Destination --> {dst_entity.title}\n')

        print(f"Fetching messages from src_chat {src_entity.title}...")
        collector_for_all_message_ids_in_src_chat = []
        last = 0
        while True:
            print(".",end="",flush=True)
            messages = await tg.get_messages(src_chat, limit=10, min_id=last)
            if not messages.total:
                break
            for m in messages:
                collector_for_all_message_ids_in_src_chat.append(m.id)
            last = messages[-1].id
            last_mes = messages[-1]

            print(f"last message:{last} ::: {last_mes.message}")
            print(f'list of messages: {collector_for_all_message_ids_in_src_chat}')

            if last != 0:
                break

        print(f"Got a total of {len(collector_for_all_message_ids_in_src_chat)} messages")
        print()

        print(f"Fetching messages from dst_chat {dst_entity.title}...")
        collector_for_all_message_ids_in_dst_chat = []
        last = 0
        while True:
            print(".",end="",flush=True)
            messages = await tg.get_messages(dst_chat, limit=10, min_id=last)
            if not messages.total:
                break
            for m in messages:
                collector_for_all_message_ids_in_dst_chat.append(m.id)
            last = messages[-1].id
            last_mes = messages[-1]

            print(f"last message id:{last}:::: {last_mes.message} ")

            if last != 0:
                break

        print("Processing...")
        for message_id in reversed(collector_for_all_message_ids_in_src_chat): #the last message or first message when reversed prints out channel name!
            #print(".",end="",flush=True)
            # if message_id in message_copy_dict:
            #     print(f"found: {message_id} in dict {message_copy_dict[message_id]}")
            #     #print(collector_for_all_message_ids_in_dst_chat)
            #     if not message_copy_dict[message_id] in collector_for_all_message_ids_in_dst_chat:
            #         print(f"{message_copy_dict[message_id]} not in collector_for_all_message_ids_in_dst_chat")
            #     continue
            try:
                print('copyin message')
                # peer =await tg.get_entity(src_chat)
                message = await tg.get_messages(src_chat, ids=message_id)

                # # Check if the message is of type Message and not MessageService
                if not isinstance(message, Message):
                    print("Fetched message is a <MessageService> Object instead of a <Message> object .")
                    print(f"\n {message} \n sourceID {src_chat}")
                    continue

                send_message_result = await copy_message(tg, dst_entity, message)
            except Exception as e:
                print(message)
                print (f"Failed to a send message: {e}")
                return None

            print(f"sent message:{send_message_result} ")
            continue





        r = await tg.get_messages(dst_chat, limit=10)
        new_message_id = r[0].id
        print(f"created link: {message_id} => {new_message_id}")
        message_copy_dict.update({message_id: new_message_id})



        print("...done.")

        makedirs("data",exist_ok=True)
        with open("data/message_copy_dict.pickle", "wb") as f:
            pickle.dump(message_copy_dict, f)

    #tg.idle()






if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    # asyncio.run(main())
