import aiohttp
import bencoder
import ipaddress
import socket
import struct

from torrent import Torrent
from util import LOG, PEER_ID

class Tracker(object):
    def __init__(self, torrent : Torrent):
        self.torrent = torrent
        self.tracker_url = torrent.announce_url
        self.peers = []
    
    async def get_peers(self):
        peers_resp = await self.request_peers()
        if b'failure reason' in peers_resp: # I added this
            LOG.error('Request to tracker for Peers failed with reason : {}'.peers_resp[b'failure reason'])
            return
        peers = self.parse_peers(peers_resp[b'peers'])
        return peers
    
    async def request_peers(self):
        async with aiohttp.ClientSession() as session:
            print("Announcing URL : ", self.tracker_url)
            resp = await session.get(self.tracker_url, params = self._get_request_params())
            resp_data = await resp.read()
            LOG.info('Tracker response : {}'.format(resp))
            LOG.info('Tracker response data : {}'.format(resp_data))
            peers = None
            try:
                peers = bencoder.decode(resp_data)
            except AssertionError:
                LOG.error('Failed to decode Tracker response : {}'.format(resp_data))
                LOG.error('Tracker request url {}'.format(str(resp.url).split('&')))
            return peers
    
    def _get_request_params(self):
        data = {'info_hash': str(self.torrent.info_hash)[2:-1],
                'peer_id': PEER_ID,
                'compact': 1,
                'no_peer_id': 0,
                'event': 'started',
                'port': 59696,
                'uploaded': 0,
                'downloaded': 0,
                'left': self.torrent.size}
        print(data)
        return data
    
    def parse_peers(self, peers : bytes):
        self_addr = socket.gethostbyname(socket.gethostname())
        LOG.info('Self address in {}'.format(self_addr))

        def handle_bytes(peers_data):
            peers = []
            for i in range(0, len(peers_data, 6)):
                addr_bytes, port_bytes = (peers_data[i:i+4], peers_data[i+4:i+6])
                ip_addr = str(ipaddress.IPv4Address(addr_bytes))
                if ip_addr == self_addr:
                    print('Skipping ', ip_addr)
                    continue
                port_bytes = struct.unpack('H>',port_bytes)[0]
                peers.append((ip_addr, port_bytes))
            return peers

        def handle_dict(peers):
            raise NotImplementedError
    
        handlers = {bytes: handle_bytes, dict: handle_dict}
        return handlers[type(peers)](peers)

    

