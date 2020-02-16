import time
from math import ceil
import json
import os
import spotipy
from dotenv import load_dotenv
load_dotenv()

CACHE_FILE = "./bpm-checker.json"


# Calculates the bpm of a song (roughly) by summing up the counts between a certain amount of taps. 
def determine_bpm(requested_bpm_accuracy = 8):
    print("\nTap {} times to the beat using enter key. If you made a mistake, type rs and then enter.".format(requested_bpm_accuracy))
    i = total_time = 0
    while i is not requested_bpm_accuracy:
        user_input = input("Press enter on the beat: ")
        if i > 0:
            total_time += time.time() - start_time
        if user_input == "rs":
            print("Resetting count of this number, start again now.")
            i = total_time = start_time = 0
            continue
        start_time = time.time()
        i += 1
    total_time += time.time() - start_time
    return ceil(60 * (requested_bpm_accuracy-1) / total_time)

# Function that's for getting a dictionary of all user playlists. 
def get_user_playlists(sp):
    items = []
    finished = False
    offset = 0

    user_name = sp.current_user()['display_name']
    while not finished:

        # Get playlists that the user can modify.
        current_results = sp.current_user_playlists(limit=50, offset=offset)
        items += [
            {"id": playlist['id'], "name": playlist['name']} 
            for playlist in current_results['items']
            if playlist['owner']['display_name'] == user_name or playlist['collaborative']
        ]

        # Make sure we're looping until we've got everything.
        if (offset + 50) >= current_results['total']:
            finished = True
        else:
            offset += 50
    return items

# Opens cache from local storage file.
def open_bpm_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as json_file:
            track_file = json.load(json_file)
            return {track_id:track_file[track_id] for track_id in track_file if 'bpm' in track_file[track_id]}
    else:
        return False

# Function that let's the user choose a playlist from their playlists. 
def select_playlist_id(sp):
    playlists = get_user_playlists(sp)

    print("\nYour playlists: ")
    for index in range(len(playlists)):
        print("{index: <4} {name}".format(index=index, name=playlists[index]['name']))

    is_selected = False
    while not is_selected:
        selected = int(input("\nNow type the playlist you would like to sort by number: ".strip()) or -1)
        if 0 <= selected < len(playlists): 
            is_selected = input("You are sorting list '{}', type 'y' if you want to continue.".format(playlists[selected]['name'])).lower() == "y"

    return playlists[selected]['id']


# Function that's for getting a dictionary of all user playlists. 
def get_playlist_tracks(sp, playlist_id):
    tracks = []
    offset = 0
    while True:

        # Get user's playlists.
        current_results = sp.playlist_tracks(playlist_id=playlist_id, fields="total,items(track(id,uri,name,artists(name)))", limit=50, offset=offset)
        for track_index in range(len(current_results['items'])):
            track = current_results['items'][track_index]['track']
            track['playlist_order'] = track_index
            track['artists'] = [artist['name'] for artist in track['artists']]
            tracks.append(track)

        # Make sure we're looping until we've got everything.
        if (offset + 50) > current_results['total']:
            return tracks
        else:
            offset += 50
    

# Selects the user device based on choice.
def select_user_device(sp):
    devices = sp.devices()['devices']

    print("Your devices: ")
    for index in range(len(devices)):
        print("{index: <3} {name}".format(index=index, name=devices[index]['name']))

    while True:
        device_index = int(
            input("\nSelect a device on which to play ({}): ".format(devices[0]['name'])).strip() or 0)
        if 0 <= device_index < len(devices): return devices[device_index]['id']

# Asks the user if automated music should be played.
def ask_automated_music():
    while True:
        answer = input("\nDo you want to automatically play the analysed music? Y/n: ").lower()
        if answer == "": answer = "y"
        if answer in ["y", "n"]: break;
    return answer == "y"

# Asks user for required operation per track.
def ask_track_operation():
    print("\nIf the bpm is already known, what do you want to do?")
    print("0) Replace the previously noted bpm")
    print("1) Average with the previously noted bpm")
    print("2) Use the known bpm and skip the song")
    while True:
        answer = int(input("Answer (0): ") or 0)
        if 0 <= answer <= 2: return answer

# Uses spotipy's function to set the right order in a playlist. Preserves added_by_date. 
def sort_playlist_based_on_tracks(sp, playlist_id, tracks = []):
    user_id = sp.current_user()['id']
    tracks_id = [track['id'] for track in tracks]
    sp.user_playlist_replace_tracks(user_id, playlist_id=playlist_id, tracks=tracks_id)


# =========================== Non Function Code ============================ #

# Setting up the Spotify-client using online authentication. We require a lot of credentials. :')
token = spotipy.util.prompt_for_user_token(
    "",
    'playlist-read-collaborative user-read-playback-state \
        playlist-modify-public playlist-read-private \
        playlist-modify-private streaming \
        user-modify-playback-state',
    client_id=os.getenv('CLIENT_ID'), 
    client_secret=os.getenv('CLIENT_SECRET'),
    redirect_uri='http://localhost:5710/callback/')
if not token:
    print("Something went wrong while logging in.")
    quit()
sp = spotipy.Spotify(auth=token)

# Make user select a playlist to analyse and get the tracks
playlist_id = select_playlist_id(sp)
tracks = get_playlist_tracks(sp, playlist_id = playlist_id)

# Ask for the amount of taps, amount of skipped seconds, operation per track and automatic play option.
taps = int(input("Taps to enter per song (8): ") or 8)
standard_skip = int(input("Seconds headstart in songs (30): ") or 30)*1000
track_operation = ask_track_operation()
automated_music = ask_automated_music()
if automated_music: device_id = select_user_device(sp)

# Open bpm database (local cache).
bpm_database = open_bpm_cache()

# Start analysing the songs. This is in a try_catch loop, so we don't lose analysed songs.
print("\nWe're starting the sorting of songs now.")
try: 
    
    # Loop over the index of all tracks in the playlist.
    for track_index in range(len(tracks)):

        # Get current track based on index, get the known bpm if it exists.
        track = tracks[track_index]
        track_bpm_known = (bpm_database and track['id'] in bpm_database and 'bpm' in bpm_database[track['id']])

        # If we already have the track information and operation is to skip it, skip it.
        if track_bpm_known and track_operation == 2:
            continue

        # Sleep a bit to give the user a bit of rest.
        time.sleep(0.5)
        print("Analysing {name} by {artist}".format(name=track['name'], artist=", ".join(track['artists'])))
        
        # Play music if user requested it.
        if automated_music: 
            sp.start_playback(device_id=device_id, uris=[track['uri']])
            sp.seek_track(position_ms=standard_skip, device_id=device_id)

        # Determining the bpm
        bpm = determine_bpm(taps)
        print("You determined this song on {} bpm.".format(bpm))

        # Averaging this bpm with the one already noted, if the user requested so.
        if track_bpm_known and track_operation == 1:
            old_bpm = bpm_database[track['id']]
            bpm = (bpm+old_bpm) / 2
            print("Noted bpm was {}, wrote down {} bpm as average.".format(old_bpm, bpm))

        # Pause playback, note bpm and continue loop.
        print("")
        sp.pause_playback(device_id=device_id)
        tracks[track_index]['bpm'] = bpm
        bpm_database[track['id']] = tracks[track_index]

    # Sort the playlist and submit it to Spotify.
    tracks.sort(key=lambda track: track['bpm'] if 'bpm' in track else 9999)
    sort_playlist_based_on_tracks(sp, playlist_id=playlist_id, tracks=tracks)

# Catch exceptions.
except BaseException as e: 
    print(str(e))
    print("Something went wrong while analysing. Songs until now have been saved. Nothing is sorted.")

# Write the user's work to the disk.
with open(CACHE_FILE, "w") as json_file:
    json_file.write(json.dumps(bpm_database))

# We're done here folks!
print("===== All {} tracks finished processing! ====".format(len(tracks)))