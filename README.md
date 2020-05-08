# py_torrent
An attempt to build a very basic bitorrent client.<br>
The code is inspired by SimplyAhmazing's BAT_TORRENT repository and youtube tutorial.

To run the project begin with installing the requirements by running `pip install -r requirements.txt`
Then to start a torrent download enter `python client.py <name of torrent file.torrent>`

Current status - Not functioning, there are issues with communication. As the client is coded with async http library I'm unable to figure out how to connect with trackers using a udp protocol. Any help is welcome.

Read - http://bittorrent.org/beps/bep_0003.html for bittorrent protocol specification.

To read the code start with the download function in client.py file and then move to read each class in the order in which they appear in the code (ps. the sessions, peice and block classes should be read after one has gone through the Tracker class)
