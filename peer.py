import asyncio
import bitstring
import struct

from client import DownloadSession
from util import LOG, PEER_ID, REQUEST_SIZE

class Peer(object):
    def __init__(self, session : DownloadSession, host, port):
        self.session = session
        self.host= host
        self.session = session
        self.peer_choke = True
        self.have_pieces = bitstring.BitArray(bin = '0'* self.session.num_pieces)
        self.pieces_in_progress = None
        self.blocks = None


        self.inflight_requests = 0

    def handshake(self):
        # see bittorrent protocol for string format
        return struct.pack('>B19s8x20s20s',19,'BitTorrent Protocol',
                            self.session.torrent.info_hash, PEER_ID.encode())

    async def interested(self, writer : asyncio.StreamWriter):
        msg = struct.pack('>Ib',1,2)
        writer.write(msg)
        await writer.drain() 

    def get_block_generator(self):
        def blocks():
            while True:
                piece = self.session.get_piece_request(self.have_pieces)
                LOG.info('[{}] generating blocks for piece {}'.format(self, piece))
                for block in piece.blocks:
                    yield block
        
        if not self.blocks:
            self.blocks = blocks()
        
        return self.blocks
    
    async def request_a_piece(self, writer : asyncio.StreamWriter):
        if self.inflight_requests > 1:
            return
        
        block_generator = self.get_block_generators()
        block = next(block_generator)

        LOG.info('[{}] Request Block {}'.format(self, block))
        msg = struct.pack('IbIII', 13, 6, block.piece, block.begin, block.length)
        writer.write(msg)
        self.inflight_requests += 1
        await writer.drain()


    async def download(self):
        retries = 0
        while retries < 5:
            retries = retries + 1
            try:
                await self._download()
            except asyncio.TimeoutError:
                LOG.warning("Timed out connection with host {}".format(self.host))
    
    async def _download(self):
        try:
            reader, writer = await asyncio.wait_for(
                                   asyncio.open_connection(self.host, self.port),
                                   timeout=10)
        except TimeoutError:
            LOG.error('Failed to connect to peer {}'.format(self.host))
            return
        
        LOG.info('{} sending handshake'.format(self))
        writer.write(self.handshake())
        await writer.drain()

        hndshake = await reader.read(68)

        await self.interested(writer)

        buf = b''
        while True:
            resp = await reader.read(REQUEST_SIZE)

            buf+=resp

            if not buf and not resp:
                return
            
            while True:

                if len(buf) < 4:
                    break

                length = struct.unpack('>I', buf[0:4])[0]

                if not len(buf) >= length:
                    break

                def consume(buf):
                    buf = buf[4+length:]
                    return buf
                
                def get_data(buf):
                    return buf[:4+length]
                
                if length == 0:
                    LOG.info('[Message] keep alive')
                    buf = consume(buf)
                    data = get_data(buf)
                    LOG.info('[Data]',data)
                    continue
                    
                if len(buf) < 5:
                    LOG.info('Buffer is less than 5 bytes...breaking')
                    break

                msg_id = struct.unpack('>b', buf[4:5])[0]

                if msg_id == 0:
                    LOG.info('[Message] CHOKE')
                    data = get_data(buf)
                    buf = consume(buf)
                    LOG.info('[DATA] {}'.format(data))
                elif msg_id == 1:
                    LOG.info('[Message] UNCHOKE')
                    data = get_data(buf)
                    buf = consume(buf)
                    self.peer_choke = False
                elif msg_id == 2:
                    LOG.info('[Message] INTERESTED')
                    data = get_data(buf)
                    buf = consume(buf)
                elif msg_id == 3:
                    LOG.info('[Message] UNINTERESTED')
                    data = get_data(buf)
                    buf = consume(buf)
                elif msg_id == 4:
                    buf = buf[5:]
                    data = get_data(buf)
                    buf = consume(buf)
                    LOG.info('[Message] HAVE')

                elif msg_id == 5:
                    bitfield = buf[5:4+length]
                    self.have_pieces = bitstring.BitArray(bitfield)
                    LOG.info('[Message] Bitfield {}'.format(bitfield))

                    buf = buf[4+length:]
                    await self.interested(writer)
                elif msg_id == 7:
                    self.inflight_requests -= 1
                    data = get_data(buf)
                    buf = consume(buf)

                    l = struct.unpack('>I', data[:4])[0]
                    try:
                        parts = struct.unpack('>IbII'+str(l-9)+'s', data[:length+4])
                        piece_idx, begin, data = parts[2], parts[3], parts[4]
                        self.session.on_block_received(piece_idx, begin, data)
                    except struct.error:
                        LOG.error("Error decoding piece")
                        return None
                else:
                    LOG.info('Unknown message id {}'.format(msg_id))
                    if msg_id == 159:
                        exit(1)
                
                await self.request_a_piece(writer)
    
    def __repr__(self):
        return "Peer {}:{}".fomrat(self.host, self.port)
                    
                






