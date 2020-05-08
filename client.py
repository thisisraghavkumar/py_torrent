import asyncio
from bitstring import BitArray
import hashlib
import logging
from pprint import pformat
import sys
from typing import List, Dict

from file_saver import FileSaver
from torrent import Torrent
from tracker import Tracker
from util import LOG, REQUEST_SIZE

logging.basicConfig(level=logging.INFO, 
                    format='%(levelname)7s: %(message)s', 
                    stream=sys.stderr)

class Piece(object):
    def __init__(self, index : int, blocks : list):
        self.index : int = index
        self.blocks: list = blocks
        self.downloaded_blocks = BitArray(bin='0'*len(blocks))
    
    def flush(self):
        [block.flush() for block in self.blocks]
    
    def is_complete(self):
        '''Returns true if all the blocks have been downloaded'''
        return all(self.downloaded_blocks)
    
    def save_block(self, begin : int, data : bytes):
        '''Writes data in block object'''
        for block_idx, block in enumerate(self.blocks):
            if block.begin == begin:
                block.data = data
                self.downloaded_blocks[block_idx] = True
    
    @property
    def data(self) -> bytes:
        return b''.join([block.data for block in self.blocks])
    
    @property
    def hash(self):
        return hashlib.sha1(self.data).digest()

    def __repr__(self):
        return '<Piece : {} Blocks : {}>'.format(self.index, len(self.blocks))
    
class Block(object):
    def __init__(self, piece_index, begin, length):
        self.piece : int = piece_index
        self.begin = begin
        self.length = length
        self.data = None

    def flush(self):
        '''Sets the data in the block to `None`'''
        self.data = None

    def __repr__(self):
        return '[Block ({}, {}, {})]'.format(self.piece, self.begin, self.length)



class DownloadSession(object):
    def __init__(self, torrent: Torrent, received_blocks : asyncio.Queue):
        self.torrent = torrent
        self.piece_size = torrent[b'info'][b'piece length']
        self.num_pieces = int(torrent.size/self.piece_size)
        self.pieces : List[Piece] = self.get_pieces()
        self.pieces_in_progress : Dict[int, Piece] = {}
        self.received_pieces : Dict[int, Piece] = {}
        self.received_blocks : asyncio.Queue = received_blocks
    
    
    def get_pieces(self) -> list:
        
        # Todo : fix bugs where block are unecessarily generated for files less than 
        #        REQUEST_SIZE
        pieces = []
        blocks_per_piece = int(self.piece_size / REQUEST_SIZE)
        for piece_idx in range(self.num_pieces):
            blocks = []
            for block_idx in range(blocks_per_piece):
                is_last_block = block_idx == (blocks_per_piece-1)
                block_length = (self.piece_size%REQUEST_SIZE or REQUEST_SIZE  #this line finds the size of the last block, it can lie in range [1,REQUEST_SIZE], if piece size is a multiple of request size then piece_size%request_size yeilds zero in which case the block size is equal to request_size
                                if is_last_block 
                                else REQUEST_SIZE
                               )
                blocks.append(Block(piece_idx, block_length*block_idx, block_length))
            pieces.append(Piece(piece_idx, blocks))
        return pieces

    def on_block_received(self, piece_index, begin, data):
        '''Implements writing off pieces after download is finished
        
        Removes pieces from `self.pieces` \n
        Verifies Piece hash \n
        Sets `self.have_pieces[piece_index]` to True if hash verifies \n
        Else reinserts piece to `self.pieces`
        '''
        piece = self.piece[piece_index]
        piece.save_block(begin, data)

        if not piece.is_complete():
            return
        
        piece_data = piece.data
        res_hash = hashlib.sha1(piece_data).digest()
        exp_hash = self.torrent.get_piece_hash(piece_index)

        self.pieces_in_progress.pop(piece.index) # I added this
        
        if res_hash != exp_hash:
            # todo - re-enqueue request for this piece
            LOG.info('Hash check failed for piece {}'.format(piece_index))
            piece.flush()
            return
        else:
            import pdb; pdb.set_trace()
            LOG.info('Hash for piece {} is valid'.format(piece_index))
            
        self.received_pieces[piece.index] = piece # I added this.

        self.received_blocks.put_nowait((piece_index*self.piece_size, data))
    
    def get_piece_request(self, have_pieces):
        '''Determine next piece to be downloaded. Expects a bitarray of pieces that can be downloaded'''

        for piece in self.pieces:
            is_piece_downloaded = piece.index in self.received_pieces
            is_piece_in_progress= piece.index in self.pieces_in_progress

            # skipping pieces already in place
            if is_piece_downloaded or is_piece_in_progress:
                continue
                
            if have_pieces[piece.index]:
                self.pieces_in_progress[piece.index] = piece
                return piece
        
    def __repr__(self):
        '''Works similar to __str__ but can also return non-string values given __str__ is defined
        if not then this is the fallback and must return a string object'''
        data = {'number of pieces':self.num_pieces,
                'piece length':self.piece_size,
                'pieces':self.pieces[:5]
            }
        return pformat(data)





async def download(t_file : str, download_loc : str, loop=None):
    '''Entry point for client, initializes `Peers` and `DownloadSession` according to 
    configureation present in `t_file` which is the .torrent file and saves the 
    downloaded file to `download_loc` directory'''

    torrent = Torrent(t_file)
    LOG.info('Torrent : {}'.format(torrent))

    torrent_writer = FileSaver(download_loc, torrent) 
    session = DownloadSession(torrent, torrent_writer.get_received_blocks_queue())

    tracker = Tracker(torrent) # implement Tracker class
    peer_info = await tracker.get_peers()

    seen_peers = set()
    peers = [Peer(session, host, port) for host, port in peer_info]
    seen_peers.update([str(p) for p in peers])
    LOG.info('Peers : {}'.format(seen_peers))

    asyncio.gather([peer.download() for peer in peers])


# Entry point for program
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    loop.run_until_complete(download(sys.argv[1], '.', loop=loop))
    print("Download operation terminated ... ")
    loop.close()


