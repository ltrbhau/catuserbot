# Userbot module to help you manage a group
# Copyright (C) 2019 The Raphielscape Company LLC.

# Licensed under the Raphielscape Public License, Version 1.c (the "License");
# you may not use this file except in compliance with the License.

import asyncio
from asyncio import sleep
from datetime import datetime

from telethon.errors import (
    BadRequestError,
    ImageProcessFailedError,
    PhotoCropSizeSmallError,
)
from telethon.errors.rpcerrorlist import UserAdminInvalidError, UserIdInvalidError
from telethon.tl.functions.channels import (
    EditAdminRequest,
    EditBannedRequest,
    EditPhotoRequest,
)
from telethon.tl.functions.messages import UpdatePinnedMessageRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    ChatAdminRights,
    ChatBannedRights,
    MessageEntityMentionName,
    MessageMediaPhoto,
)

from ..utils import admin_cmd, errors_handler, sudo_cmd
from . import BOTLOG, BOTLOG_CHATID, CMD_HELP
from .sql_helper.mute_sql import is_muted, mute, unmute

# =================== CONSTANT ===================
PP_TOO_SMOL = "`The image is too small`"
PP_ERROR = "`Failure while processing the image`"
NO_ADMIN = "`I am not an admin nub nibba!`"
NO_PERM = "`I don't have sufficient permissions! This is so sed. Alexa play despacito`"
NO_SQL = "`Running on Non-SQL mode!`"

CHAT_PP_CHANGED = "`Chat Picture Changed`"
CHAT_PP_ERROR = (
    "`Some issue with updating the pic,`"
    "`maybe coz I'm not an admin,`"
    "`or don't have enough rights.`"
)
INVALID_MEDIA = "`Invalid Extension`"

BANNED_RIGHTS = ChatBannedRights(
    until_date=None,
    view_messages=True,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True,
)

UNBAN_RIGHTS = ChatBannedRights(
    until_date=None,
    send_messages=None,
    send_media=None,
    send_stickers=None,
    send_gifs=None,
    send_games=None,
    send_inline=None,
    embed_links=None,
)

MUTE_RIGHTS = ChatBannedRights(until_date=None, send_messages=True)
UNMUTE_RIGHTS = ChatBannedRights(until_date=None, send_messages=False)
# ================================================


@borg.on(admin_cmd("setgpic$"))
@errors_handler
async def set_group_photo(gpic):
    if not gpic.is_group:
        await gpic.edit("`I don't think this is a group.`")
        return
    replymsg = await gpic.get_reply_message()
    chat = await gpic.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    photo = None
    if not admin and not creator:
        await gpic.edit(NO_ADMIN)
        return
    if replymsg and replymsg.media:
        if isinstance(replymsg.media, MessageMediaPhoto):
            photo = await gpic.client.download_media(message=replymsg.photo)
        elif "image" in replymsg.media.document.mime_type.split("/"):
            photo = await gpic.client.download_file(replymsg.media.document)
        else:
            await gpic.edit(INVALID_MEDIA)
    if photo:
        try:
            await gpic.client(
                EditPhotoRequest(gpic.chat_id, await gpic.client.upload_file(photo))
            )
            await gpic.edit(CHAT_PP_CHANGED)
        except PhotoCropSizeSmallError:
            await gpic.edit(PP_TOO_SMOL)
        except ImageProcessFailedError:
            await gpic.edit(PP_ERROR)
    if BOTLOG:
        await gpic.client.send_message(
            BOTLOG_CHATID,
            "#GROUPPIC\n"
            f"Group profile pic changed "
            f"CHAT: {gpic.chat.title}(`{gpic.chat_id}`)",
        )


@borg.on(admin_cmd("promote(?: |$)(.*)"))
@errors_handler
async def promote(promt):
    chat = await promt.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await promt.edit(NO_ADMIN)
        return
    new_rights = ChatAdminRights(
        add_admins=False,
        invite_users=True,
        change_info=False,
        ban_users=True,
        delete_messages=True,
        pin_messages=True,
    )
    await promt.edit("`Promoting...`")
    user, rank = await get_user_from_event(promt)
    if not rank:
        rank = "Admin"
    if user:
        pass
    else:
        return
    try:
        await promt.client(EditAdminRequest(promt.chat_id, user.id, new_rights, rank))
        await promt.edit("`Promoted Successfully! Now gib Party`")
    except BadRequestError:
        await promt.edit(NO_PERM)
        return
    if BOTLOG:
        await promt.client.send_message(
            BOTLOG_CHATID,
            "#PROMOTE\n"
            f"USER: [{user.first_name}](tg://user?id={user.id})\n"
            f"CHAT: {promt.chat.title}(`{promt.chat_id}`)",
        )


@borg.on(admin_cmd("demote(?: |$)(.*)"))
@errors_handler
async def demote(dmod):
    chat = await dmod.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await dmod.edit(NO_ADMIN)
        return
    await dmod.edit("`Demoting...`")
    rank = "admeme"
    user = await get_user_from_event(dmod)
    user = user[0]
    if user:
        pass
    else:
        return
    newrights = ChatAdminRights(
        add_admins=None,
        invite_users=None,
        change_info=None,
        ban_users=None,
        delete_messages=None,
        pin_messages=None,
    )
    try:
        await dmod.client(EditAdminRequest(dmod.chat_id, user.id, newrights, rank))
    except BadRequestError:
        await dmod.edit(NO_PERM)
        return
    await dmod.edit("`Demoted Successfully! Betterluck next time`")
    if BOTLOG:
        await dmod.client.send_message(
            BOTLOG_CHATID,
            "#DEMOTE\n"
            f"USER: [{user.first_name}](tg://user?id={user.id})\n"
            f"CHAT: {dmod.chat.title}(`{dmod.chat_id}`)",
        )


@borg.on(admin_cmd("ban(?: |$)(.*)"))
@errors_handler
async def ban(bon):
    chat = await bon.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await bon.edit(NO_ADMIN)
        return
    user, reason = await get_user_from_event(bon)
    if user:
        pass
    else:
        return
    await bon.edit("`Whacking the pest!`")
    try:
        await bon.client(EditBannedRequest(bon.chat_id, user.id, BANNED_RIGHTS))
    except BadRequestError:
        await bon.edit(NO_PERM)
        return
    try:
        reply = await bon.get_reply_message()
        if reply:
            await reply.delete()
    except BadRequestError:
        await bon.edit("`I dont have message nuking rights! But still he is banned!`")
        return
    if reason:
        await bon.edit(f"`{str(user.id)}` is banned !!\nReason: {reason}")
    else:
        await bon.edit(f"`{str(user.id)}` is banned !!")
    if BOTLOG:
        await bon.client.send_message(
            BOTLOG_CHATID,
            "#BAN\n"
            f"USER: [{user.first_name}](tg://user?id={user.id})\n"
            f"CHAT: {bon.chat.title}(`{bon.chat_id}`)",
        )


@borg.on(admin_cmd("unban(?: |$)(.*)"))
@errors_handler
async def nothanos(unbon):
    chat = await unbon.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await unbon.edit(NO_ADMIN)
        return
    await unbon.edit("`Unbanning...`")
    user = await get_user_from_event(unbon)
    user = user[0]
    if user:
        pass
    else:
        return
    try:
        await unbon.client(EditBannedRequest(unbon.chat_id, user.id, UNBAN_RIGHTS))
        await unbon.edit("```Unbanned Successfully. Granting another chance.```")
        if BOTLOG:
            await unbon.client.send_message(
                BOTLOG_CHATID,
                "#UNBAN\n"
                f"USER: [{user.first_name}](tg://user?id={user.id})\n"
                f"CHAT: {unbon.chat.title}(`{unbon.chat_id}`)",
            )
    except UserIdInvalidError:
        await unbon.edit("`Uh oh my unban logic broke!`")


@command(incoming=True)
async def watcher(event):
    if is_muted(event.sender_id, event.chat_id):
        await event.delete()


@borg.on(admin_cmd(r"mute(?: |$)(.*)"))
async def startmute(event):
    if event.is_private:
        await event.edit("Unexpected issues or ugly errors may occur!")
        await asyncio.sleep(3)
        await event.get_reply_message()
        userid = event.chat_id
        replied_user = await event.client(GetFullUserRequest(userid))
        chat_id = event.chat_id
        if is_muted(userid, chat_id):
            return await event.edit(
                "This user is already muted in this chat ~~lmfao sed rip~~"
            )
        try:
            mute(userid, chat_id)
        except Exception as e:
            await event.edit("Error occured!\nError is " + str(e))
        else:
            await event.edit("Successfully muted that person.\n**｀-´)⊃━☆ﾟ.*･｡ﾟ **")
        if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID,
                "#PM_MUTE\n"
                f"USER: [{replied_user.user.first_name}](tg://user?id={userid})\n"
                f"CHAT: {event.chat.title}(`{event.chat_id}`)",
            )
    else:
        chat = await event.get_chat()
        user, reason = await get_user_from_event(event)
        if not user:
            return
        if user.id == bot.uid:
            return await event.edit("Sorry, I can't mute my self")
        if is_muted(user.id, event.chat_id):
            return await event.edit(
                "This user is already muted in this chat ~~lmfao sed rip~~"
            )
        try:
            await event.client(EditBannedRequest(event.chat_id, user.id, MUTE_RIGHTS))
        except UserAdminInvalidError:
            if "admin_rights" in vars(chat) and vars(chat)["admin_rights"] is not None:
                if chat.admin_rights.delete_messages is not True:
                    return await event.edit(
                        "`You can't mute a person if you dont have delete messages permission. ಥ﹏ಥ`"
                    )
            elif "creator" not in vars(chat):
                return await event.edit(
                    "`You can't mute a person without admin rights niqq.` ಥ﹏ಥ  "
                )
            try:
                mute(user.id, event.chat_id)
            except Exception as e:
                return await event.edit("Error occured!\nError is " + str(e))
        except Exception as e:
            return await event.edit(f"**Error : **`{str(e)}`")
        if reason:
            await event.edit(
                f"{user.first_name} is muted in {event.chat.title}\n"
                f"`Reason:`{reason}"
            )
        else:
            await event.edit(f"{user.first_name} is muted in {event.chat.title}")
        if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID,
                "#MUTE\n"
                f"USER: [{user.first_name}](tg://user?id={user.id})\n"
                f"CHAT: {event.chat.title}(`{event.chat_id}`)",
            )


@borg.on(admin_cmd(r"unmute(?: |$)(.*)"))
async def endmute(event):
    if event.fwd_from:
        return
    if event.is_private:
        await event.edit("Unexpected issues or ugly errors may occur!")
        await asyncio.sleep(3)
        userid = event.chat_id
        replied_user = await event.client(GetFullUserRequest(userid))
        chat_id = event.chat_id
        if not is_muted(userid, chat_id):
            return await event.edit(
                "__This user is not muted in this chat__\n（ ^_^）o自自o（^_^ ）"
            )
        try:
            unmute(userid, chat_id)
        except Exception as e:
            await event.edit("Error occured!\nError is " + str(e))
        else:
            await event.edit("Successfully unmuted that person\n乁( ◔ ౪◔)「    ┑(￣Д ￣)┍")
        if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID,
                "#UNMUTE\n"
                f"USER: [{replied_user.user.first_name}](tg://user?id={userid})\n"
                f"CHAT: {event.chat.title}(`{event.chat_id}`)",
            )
    else:
        await event.edit("```Unmuting...```")
        user = await get_user_from_event(event)
        user = user[0]
        if not user:
            return
        try:
            await event.client(EditBannedRequest(event.chat_id, user.id, UNBAN_RIGHTS))
            if is_muted(user.id, event.chat_id):
                unmute(user.id, event.chat_id)
        except Exception as e:
            return await event.edit(f"**Error : **`{str(e)}`")
        else:
            await event.edit("Successfully unmuted that person\n乁( ◔ ౪◔)「    ┑(￣Д ￣)┍")
        if BOTLOG:
            await event.client.send_message(
                BOTLOG_CHATID,
                "#UNMUTE\n"
                f"USER: [{user.first_name}](tg://user?id={user.id})\n"
                f"CHAT: {event.chat.title}(`{event.chat_id}`)",
            )


@borg.on(admin_cmd("pin($| (.*))"))
@errors_handler
async def pin(msg):
    chat = await msg.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await msg.edit(NO_ADMIN)
        return
    to_pin = msg.reply_to_msg_id
    if not to_pin:
        await msg.edit("`Reply to a message to pin it.`")
        return
    options = msg.pattern_match.group(1)
    is_silent = True
    if options.lower() == "loud":
        is_silent = False
    try:
        await msg.client(UpdatePinnedMessageRequest(msg.to_id, to_pin, is_silent))
    except BadRequestError:
        await msg.edit(NO_PERM)
        return
    await msg.edit("`Pinned Successfully!`")
    user = await get_user_from_id(msg.from_id, msg)
    if BOTLOG:
        await msg.client.send_message(
            BOTLOG_CHATID,
            "#PIN\n"
            f"ADMIN: [{user.first_name}](tg://user?id={user.id})\n"
            f"CHAT: {msg.chat.title}(`{msg.chat_id}`)\n"
            f"LOUD: {not is_silent}",
        )


@borg.on(admin_cmd("kick(?: |$)(.*)"))
@errors_handler
async def kick(usr):
    chat = await usr.get_chat()
    admin = chat.admin_rights
    creator = chat.creator
    if not admin and not creator:
        await usr.edit(NO_ADMIN)
        return
    user, reason = await get_user_from_event(usr)
    if not user:
        await usr.edit("`Couldn't fetch user.`")
        return
    await usr.edit("`Kicking...`")
    try:
        await usr.client.kick_participant(usr.chat_id, user.id)
        await sleep(0.5)
    except Exception as e:
        await usr.edit(NO_PERM + f"\n{str(e)}")
        return
    if reason:
        await usr.edit(
            f"`Kicked` [{user.first_name}](tg://user?id={user.id})`!`\nReason: {reason}"
        )
    else:
        await usr.edit(f"`Kicked` [{user.first_name}](tg://user?id={user.id})`!`")
    if BOTLOG:
        await usr.client.send_message(
            BOTLOG_CHATID,
            "#KICK\n"
            f"USER: [{user.first_name}](tg://user?id={user.id})\n"
            f"CHAT: {usr.chat.title}(`{usr.chat_id}`)\n",
        )


@borg.on(admin_cmd("iundlt$"))
async def _(event):
    if event.fwd_from:
        return
    c = await event.get_chat()
    if c.admin_rights or c.creator:
        a = await borg.get_admin_log(event.chat_id, limit=5, edit=False, delete=True)
        deleted_msg = "Deleted message in this group:"
        for i in a:
            deleted_msg += "\n👉`{}`".format(i.old.message)
        await event.edit(deleted_msg)
    else:
        await event.edit(
            "`You need administrative permissions in order to do this command`"
        )
        await asyncio.sleep(3)
        await event.delete()


@borg.on(sudo_cmd(pattern="(ban|unban)($| (.*))", allow_sudo=True))
async def _(event):
    if event.fwd_from:
        return
    datetime.now()
    to_ban_id = None
    rights = None
    input_cmd = event.pattern_match.group(1)
    if input_cmd == "ban":
        rights = BANNED_RIGHTS
    elif input_cmd == "unban":
        rights = UNBAN_RIGHTS
    input_str = event.pattern_match.group(2)
    reply_msg_id = event.reply_to_msg_id
    if reply_msg_id:
        r_mesg = await event.get_reply_message()
        to_ban_id = r_mesg.from_id
    elif input_str and "all" not in input_str:
        to_ban_id = int(input_str)
    else:
        return False
    try:
        await borg(EditBannedRequest(event.chat_id, to_ban_id, rights))
    except (Exception) as exc:
        await event.reply(str(exc))
    else:
        await event.reply(f"{input_cmd}ned Successfully!")


@borg.on(sudo_cmd(pattern="pgs($| (.*))", allow_sudo=True))
async def _(event):
    if event.fwd_from:
        return
    if event.reply_to_msg_id:
        i = 1
        msgs = []
        from_user = None
        input_str = event.pattern_match.group(1)
        if input_str:
            from_user = await borg.get_entity(input_str)
        async for message in borg.iter_messages(
            event.chat_id, min_id=event.reply_to_msg_id, from_user=from_user
        ):
            i = i + 1
            msgs.append(message)
            if len(msgs) == 100:
                await borg.delete_messages(event.chat_id, msgs, revoke=True)
                msgs = []
        if len(msgs) <= 100:
            await borg.delete_messages(event.chat_id, msgs, revoke=True)
            msgs = []
            await event.delete()
        else:
            await event.reply("**PURGE** Failed!")


async def get_user_from_event(event):
    args = event.pattern_match.group(1).split(" ", 1)
    extra = None
    if event.reply_to_msg_id:
        previous_message = await event.get_reply_message()
        user_obj = await event.client.get_entity(previous_message.from_id)
        extra = event.pattern_match.group(1)
    elif args:
        user = args[0]
        if len(args) == 2:
            extra = args[1]
        if user.isnumeric():
            user = int(user)
        if not user:
            await event.edit("`Pass the user's username, id or reply!`")
            return
        if event.message.entities:
            probable_user_mention_entity = event.message.entities[0]

            if isinstance(probable_user_mention_entity, MessageEntityMentionName):
                user_id = probable_user_mention_entity.user_id
                user_obj = await event.client.get_entity(user_id)
                return user_obj
        try:
            user_obj = await event.client.get_entity(user)
        except (TypeError, ValueError):
            await event.edit("Could not fetch info of that user.")
            return None
    return user_obj, extra


async def get_user_from_id(user, event):
    if isinstance(user, str):
        user = int(user)
    try:
        user_obj = await event.client.get_entity(user)
    except (TypeError, ValueError) as err:
        await event.edit(str(err))
        return None
    return user_obj


CMD_HELP.update(
    {
        "admin": ".setgpic <reply to image>\
\nUsage: Changes the group's display picture\
\n\n.promote <username/reply> <custom rank (optional)>\
\nUsage: Provides admin rights to the person in the chat.\
\n\n.demote <username/reply>\
\nUsage: Revokes the person's admin permissions in the chat.\
\n\n.ban <username/reply> <reason (optional)>\
\nUsage: Bans the person off your chat.\
\n\n.unban <username/reply>\
\nUsage: Removes the ban from the person in the chat.\
\n\n.mute <username/reply> <reason (optional)>\
\nUsage: Mutes the person in the chat, works on admins too.\
\n\n.unmute <username/reply>\
\nUsage: Removes the person from the muted list.\
\n\n.pin <reply>\
\nUsage: Pins the replied message in Group\
\n\n.kick <username/reply> \
\nUsage: kick the person off your chat.\
\n\n.iundlt\
\nUsage: display last 5 deleted messages in group."
    }
)
