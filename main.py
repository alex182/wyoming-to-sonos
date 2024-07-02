from soco import SoCo
import argparse
import asyncio
import logging
import time
import http.server
import requests
import uuid
import os
from pydub import AudioSegment
from functools import partial
from threading import Thread

from wyoming.event import Event
from wyoming.server import AsyncEventHandler, AsyncServer

_LOGGER = logging.getLogger()
_HOST_IP = os.environ['HOST_IP']
_SONOS_IP = os.environ['SONOS_IP']
_PIPER_IP = os.environ['PIPER_IP']
_VOICE_MODEL = os.environ['VOICE_MODEL']


def run(server_class=http.server.HTTPServer, handler_class=http.server.SimpleHTTPRequestHandler):
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    _LOGGER.debug(args)

    _LOGGER.info("Ready")

    server = AsyncServer.from_uri(f'tcp://0.0.0.0:10500')

    try:
        thread = Thread(target = run)
        thread.start()
        await server.run(partial(SonosEventHandler, args))
    except KeyboardInterrupt:
        pass

class SonosEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        cli_args: argparse.Namespace,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.client_id = str(time.monotonic_ns())

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        _LOGGER.info(event)

        _LOGGER.info(event.type)

        ttsFile = ''
        if(event.type == 'detection'):
            self.sendToSonos(_SONOS_IP,f'http://{_HOST_IP}:8080/sound_files/tts_start.mp3')
        if(event.type == 'error'):
            text_value = event.data.get('text')
            ttsFile = self.getTTS(text_value)
            self.sendToSonos(_SONOS_IP,f'http://{_HOST_IP}:8080/sound_files/tts_error.mp3')
            self.sendToSonos(_SONOS_IP,f'http://{_HOST_IP}:8080/sound_files/{ttsFile}')

            time.sleep(2)
            os.remove(f'./sound_files/{ttsFile}')
        if(event.type == 'synthesize'):
            text_value = event.data.get('text')
            ttsFile = self.getTTS(text_value)
            self.sendToSonos(_SONOS_IP,f'http://{_HOST_IP}:8080/sound_files/{ttsFile}')
            time.sleep(2)
            os.remove(f'./sound_files/{ttsFile}')

        return True

    def sendToSonos(self,speakerIP,fileUrl):

        sonos = SoCo(speakerIP)
        sonos.play_uri(fileUrl)
        sonos.play()

    def getTTS(self,text):
        headers = {
        'Content-Type': 'application/json',
        }

        json_data = {
            'text': text,
            'voice': f'{_VOICE_MODEL}',
        }

        response = requests.post(f'http://{_PIPER_IP}:8080/api/tts', headers=headers, json=json_data)

        uuid.uuid4()
        uuidString = str(uuid.uuid4())
        fileName=f'./sound_files/{uuidString}.wav'
        with open(fileName, 'wb') as f:
            f.write(response.content)

        AudioSegment.from_wav(fileName).export(f"./sound_files/{uuidString}.mp3", format="mp3")

        os.remove(fileName)
        return f'{uuidString}.mp3'

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass