import bencoder
from pprint import pformat
import hashlib
import copy

class Torrent(object):
    def __init__(self, path:str):
        '''Torrent object initialized with the torrent file found at `path`'''
        self.path = path
        self.info = self.read_torrent_file(self.path)
    
    # this is defined so that [] operator can be used with a Torrent object
    # if t = Torrent(), then t[key] will return t.info[key] 
    def __getitem__(self, item):
        return self.info[item]
    
    @property
    def announce_url(self):
        '''returns the tracker's `url`'''
        return self.info[b'announce'].decode('utf-8')
    
    @property
    def size(self):
        '''returns the `size` of the torrent file in number of bytes'''

        info = self.info[b'info']
        if b'length' in info:
            return info[b'length']
        else:
            return sum([f[b'length'] for f in info[b'files']])
    
    @property
    def info_hash(self):
        return hashlib.sha1(bencoder.encode(self.info[b'info'])).digest()

    def get_piece_hash(self, i):
        '''
        returns hash of the `i`th piece
        '''
        return self.info[b'info'][b'pieces'][i*20 : (i*20)+20]  #hash of every piece is 20 bytes long

    def read_torrent_file(self, path: str):
        '''
        read the torrent file present at `path` and returns the decoded data
        '''
        with open(path, 'rb') as f:
            return bencoder.decode(f.read())
    
    def __str__(self):
        return pformat(self.info)