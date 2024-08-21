import asyncio

from src import Spammer

from src import get_config
from src import get_session_files
from src import get_folders_links
from src import get_proxy


async def main():
    proxy = await get_proxy()
    config = await get_config()
    sessions = await get_session_files('sessions')
    spammer_data = {
        'folders': await get_folders_links(),
        'api_id': config['api_id'],
        'api_hash': config['api_hash'],
        'proxy': proxy,
        'text': config['text']
    }
    await Spammer(sessions, spammer_data).start()


if __name__ == '__main__':
    asyncio.run(main())
