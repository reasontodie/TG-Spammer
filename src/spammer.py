import socks
import random
import asyncio
from itertools import cycle

from datetime import datetime
from datetime import timedelta

from loguru import logger

from telethon.types import User
from telethon import TelegramClient

from telethon.errors import FloodError
from telethon.errors import FloodWaitError
from telethon.errors import ChannelPrivateError
from telethon.errors import MessageIdInvalidError
from telethon.errors import UserBannedInChannelError
from telethon.errors import ChatWriteForbiddenError
from telethon.errors import UserNotParticipantError
from telethon.errors import SlowModeWaitError

from telethon.tl.functions.chatlists import LeaveChatlistRequest
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest
from telethon.tl.functions.chatlists import JoinChatlistInviteRequest

from telethon.tl.functions.messages import UpdatePinnedMessageRequest

from telethon.tl.types.chatlists import ChatlistInviteAlready
from telethon.types import InputChatlistDialogFilter

from .models import SpammerData

from .utils import get_config
from .utils import msg_randomizing


class Spammer:
    def __init__(self, sessions: list, data: SpammerData):
        if not sessions:
            raise ValueError('Забыли сессии добавить')

        self.api_id = data['api_id']
        self.api_hash = data['api_hash']
        self.folders_links = data['folders']
        self.proxy = data['proxy']
        self.text = data['text']

        self.sessions = sessions
        self.sessions_iter = cycle(self.sessions)
        self.session: TelegramClient | None = None

        self.me: User | None = None
        self.folder_url: str | None = None
        self.folder = None
        self.current_chat = None

        self.flood_list = {}
        self.current_retry = 1
        self.max_retry = len(sessions)
        self.dead_session = []

    @staticmethod
    async def __log_info(message: str) -> None:
        logger.info(message)

    @staticmethod
    async def __log_error(message: str) -> None:
        logger.error(message)

    @staticmethod
    async def __log_success(message: str) -> None:
        logger.success(message)

    async def __update_text(self):
        self.text = (await get_config())['text']

    async def __flood_wait(self, err: FloodWaitError | FloodError) -> None:
        delta = timedelta(seconds=err.seconds)
        self.flood_list[self.me.id] = datetime.now() + delta
        await self.__log_info(f'User: {self.me.username} | Phone: {self.me.phone} словил флуд ошибку, ушел спать.')
        await self.__next_session()

    async def __user_in_flood(self) -> bool:
        if flood := self.flood_list.get(self.me.id):
            if datetime.now() >= flood:
                del self.flood_list[self.me.id]
                return False
            return True
        return False

    async def __closest_session(self) -> float:
        now = datetime.now()
        nearest_time = min(self.flood_list.values(), key=lambda d: (d - now).total_seconds())
        sleep_seconds = (nearest_time - now).total_seconds()
        return max(sleep_seconds, 0)
    
    async def __unpack_proxy(self) -> tuple:
        if self.proxy:
            ip, port, login, password = (random.choice(self.proxy)).split(':')
            return socks.SOCKS5, ip, int(port), True, login, password

    async def __next_session(self) -> None:
        if len(self.dead_session) == len(self.sessions):
            raise ValueError('Все сессии умерли')

        if self.session and self.me:
            await self.session.disconnect()

        if (self.current_retry > self.max_retry) and self.me:
            wait = await self.__closest_session()
            await self.__log_info(f'Все аккаунты с флуд ошибкой, ближайшее снятие через: {wait} секунд')
            self.current_retry = 1
            await asyncio.sleep(wait)

        while (session := next(self.sessions_iter)) in self.dead_session:
            pass
        proxy = await self.__unpack_proxy()
        self.session = TelegramClient(session, self.api_id, self.api_hash, proxy=proxy)
        await self.session.connect()
        self.me = await self.session.get_me()

        if self.me:
            if not await self.__user_in_flood():
                if self.folder and self.folder_url:
                    await self.__join_folder_pool(self.folder_url)
                    await self.__send_message(self.current_chat)
                self.current_retry = 1
                await self.__log_success(f"Вошел как: {await self.__user_string()}")
                return
        if self.me is None:
            await self.__log_error(f'Мертвая сессия: {session}. Пропускаем')
            self.dead_session.append(session)
        self.current_retry += 1
        await self.__next_session()

    async def __join_folder(self, link: str) -> ChatlistInviteAlready:
        try:
            folder_hash = link.replace("https://t.me/addlist/", "")
            result = await self.session(CheckChatlistInviteRequest(slug=folder_hash))
            if isinstance(result, ChatlistInviteAlready):
                await self.__log_info(f"Не удалось вступить. Папка уже добавлена в аккаунт: {link}")
                return result
            else:
                result = await self.session(JoinChatlistInviteRequest(slug=folder_hash, peers=result.peers))
                await self.__log_success(f"Успешно зашел в папку: {link}")
                return result
        except (FloodError, FloodWaitError) as err:
            await self.__log_error(
                f"Ошибка: {err} при добавлении папки на аккаунте {await self.__user_string()}")
            await self.__flood_wait(err)

    @staticmethod
    async def __collect_for_ping(iter_data: ()) -> list:
        mention_text = []
        async for user in iter_data:
            user: User = user
            if not user.premium:
                mention_text.append('[{}](tg://user?id={})'.format('.', user.id))
        return mention_text

    async def __user_string(self):
        return f"User: @{self.me.username} | Phone: {self.me.phone}"

    async def __send_message(self, chat) -> None:
        try:
            permissions = await self.session.get_permissions(chat, self.me)
            text = await msg_randomizing(self.text)
            if permissions.pin_messages:
                msg = await self.session.send_message(chat, text)
                pin = await self.session(UpdatePinnedMessageRequest(chat, msg.id, silent=False))
                await self.session.delete_messages(chat, [pin.updates[0].id])
            else:
                jar_size = 200
                mentions = await self.__collect_for_ping(self.session.iter_participants(chat))
                chunks = [mentions[i:i + jar_size] for i in range(0, len(mentions), jar_size)]

                msg = await self.session.send_message(chat, ''.join(random.choice(chunks)))
                await self.session.edit_message(chat, msg, text)
                await asyncio.sleep(1.3)
            await self.__log_info(f'{await self.__user_string()} отправил сообщение в чат {chat.title}')
        except (FloodError, FloodWaitError) as err:
            self.current_chat = chat
            await self.__flood_wait(err)
        except UserBannedInChannelError:
            await self.__log_error(f'{await self.__user_string()} забанен в чате. Пропускаем')
        except ChatWriteForbiddenError:
            await self.__log_error(f'{await self.__user_string()} нет прав писать в чате. Пропускаем')
        except (UserNotParticipantError, ChannelPrivateError):
            await self.__log_error(f'{await self.__user_string()} нету в чате (Ошибка тг, либо не приняли). Пропускаем')
        except MessageIdInvalidError:
            await self.__log_error(f'{await self.__user_string()} антиспам-бот в группе снес сообщение, скипаем.')
        except SlowModeWaitError:
            await self.__log_error(f'{await self.__user_string()} в группе SlowMode, скипаем.')

    async def __join_folder_pool(self, link: str) -> None:
        while not (folder := await self.__join_folder(link)):
            await asyncio.sleep(0.3)
        self.folder_url = link
        self.folder = folder

    async def __leave_folder(self):
        req = LeaveChatlistRequest(
            chatlist=InputChatlistDialogFilter(filter_id=self.folder.filter_id), peers=self.folder.already_peers
        )
        await self.session(req)
        await self.__log_info(f'{await self.__user_string()} вышел с папки ')

    async def __unlock_spambot(self):
        bot = await self.session.get_entity('@SpamBot')
        await self.session.send_message(bot, '/start')
        await asyncio.sleep(3)
        message = await self.session.send_message(bot, '/start')
        await asyncio.sleep(2)
        chat = await self.session.get_messages(bot, ids=[message.id+1])
        if 'К сожалению' in chat[0].text or "I'm afraid" in chat[0].text:
            await self.__log_error(f'{await self.__user_string()} спам блок не был снят')
            return
        await self.__log_success(f'{await self.__user_string()} cпам блок был снят')

    async def start(self) -> None:
        if not self.session: await self.__next_session()
        for link in self.folders_links:
            await self.__update_text()
            await self.__join_folder_pool(link)
            try:
                for chat in self.folder.chats:
                    await self.__send_message(chat)
                    await asyncio.sleep(1.5)
            except IndexError:
                pass
            await self.__unlock_spambot()
            await self.__leave_folder()
