import os
import json
import random

from .models import SpammerData


async def msg_randomizing(text: str):
    random_chars = {
        'З': '3', 'о': 'o', 'О': '0',
        'Н': 'H', 'А': 'A', 'а': 'a',
        'У': 'Y', 'у': 'y', 'М': 'M',
        'Т': 'T', 'т': 't', 'С': 'C',
        'с': 'c', 'р': 'p', 'Р': 'P',
        'Е': 'E', 'В': 'B', 'х': 'x',
        'б': '6', 'м': 'm', 'п': 'n',
        'Б': '6', 'ь': 'b', 'Ь': 'b',
        'ц': 'u', 'К': 'K', 'к': 'k',
        'И': 'N', 'ч': '4', 'и': 'u',
        'Ч': '4', 'з': '3', 'Х': 'X'
    }
    msg = []
    for char in text:
        if random.randint(0, 1) == 1:
            msg.append(char) if not random_chars.get(char) else msg.append(random_chars.get(char))
        else:
            msg.append(char)
    return ''.join(msg)


async def get_session_files(directory='sessions'):
    session_files = [f'{directory}/{f}' for f in os.listdir(directory) if f.endswith('.session')]
    return session_files


async def get_folders_links():
    with open('links.txt', 'r', encoding='utf-8') as f:
        return [link.replace('\n', '') for link in f.readlines()]
    
    
async def get_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


async def get_proxy():
    with open('proxy.txt', 'r', encoding='utf-8') as f:
        return [line.replace('\n', '') for line in f.readlines()]