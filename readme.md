# Spotify BPM sorter
This simple python application helps you manually sort your spotify playlists if the built-in sorting is not working for you. As I dance lots of Salsa and want to order these songs (and spotify doesn't know how to sort them), I built this. 

## Functions
* Lets you choose a playlist and tap enter to determine the bpm per song.
* Automatically plays the right song on Spotify in order to have easy listening.
* Caches songs you've checked in the past to prevent double work.
* Has a safe fallback in case of problems.

## Installation
Tested on Python 3.7 or higher. Comes with "it works on my machine"-guarantees. Install recommended using a virtualenv and the requirements.txt file. 

## Spotify-development
Built on top of the amazing [Spotipy Library](https://spotipy.readthedocs.io/en/2.9.0/) For using this app you do need a [Spotify-development Web-API link](https://developer.spotify.com/documentation/web-api/). Read more about this in the link. Don't forget to enable the callback-point `http://localhost/` in your spotify web-api settings!