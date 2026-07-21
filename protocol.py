import asyncio
import struct
import websockets


class WsProtocol:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.buffer = bytearray()
        self.on_message = None
        self.on_disconnect = None

    async def connect(self, uri):
        self.ws = await websockets.connect(
            uri,
            additional_headers={"x-client-type": "agent"}
        )
        self.connected = True
        asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for message in self.ws:
                if isinstance(message, bytes):
                    self.buffer.extend(message)
                    while len(self.buffer) >= 5:
                        payload_len = struct.unpack(">I", self.buffer[:4])[0]
                        total = 5 + payload_len
                        if len(self.buffer) < total:
                            break
                        msg_type = self.buffer[4]
                        payload = bytes(self.buffer[5:total])
                        if self.on_message:
                            asyncio.create_task(self.on_message(msg_type, payload))
                        self.buffer = self.buffer[total:]
        except Exception:
            pass
        finally:
            self.connected = False
            if self.ws:
                await self.ws.close()
                self.ws = None
            if self.on_disconnect:
                asyncio.create_task(self.on_disconnect())

    async def send(self, msg_type, payload=None):
        if not self.connected or not self.ws:
            return
        payload = payload or b""
        frame = struct.pack(">I", len(payload)) + struct.pack("B", msg_type) + payload
        try:
            await self.ws.send(frame)
        except Exception:
            self.connected = False

    async def send_json(self, msg_type, obj):
        import json
        data = json.dumps(obj).encode("utf-8")
        await self.send(msg_type, data)
