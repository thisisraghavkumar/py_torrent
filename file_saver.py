import asyncio
import os
from util import LOG

class FileSaver(object):
    def __init__(self, out_dir, torrent):
        self.file_name = self.get_file_name(out_dir, torrent)
        # using os.open instead of open for low level i/o
        self.fd = os.open(self.file_name, os.O_RDWR|os.O_CREAT)
        self.received_blocks_queue = asyncio.Queue()
        # asyncio.ensure_future(self.start()) used pre python 3.7, instead use -
        asyncio.create_task(self.start())

    def get_received_blocks_queue(self):
        return self.received_blocks_queue

    def get_file_name(self, out_dir, torrent, i=0):
        name = torrent[b'info'][b'name'].decode('utf-8')
        # adds a number to file name
        if i != 0:
            name = name+f'-({i})'
        path_name = os.path.join(out_dir, name)
        if os.path.exists(path_name):
            return self.get_file_name(out_dir, torrent, i+1)
        else:
            return path_name
    
    async def start(self):
        while True:
            block = await self.get_received_blocks_queue().get()

            if not block:
                LOG("Received poison pill. Exiting.")
            
            block_abs_location, block_data = block

            os.lseek(self.fd,block_abs_location,os.SEEK_SET)
            os.write(self.fd, block_data)