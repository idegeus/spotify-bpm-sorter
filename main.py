import time
from math import ceil
import json
import os, traceback
import sys
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
            {"id": playlist['id'], "name": playlist['name'], "snapshot_id": playlist['snapshot_id']} 
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
            if not track_file: return {}
            return {track_id:track_file[track_id] for track_id in track_file if 'bpm' in track_file[track_id]}
    else:
        return {}

# Function that let's the user choose a playlist from their playlists. 
def select_playlist(sp):
    playlists = get_user_playlists(sp)

    print("\nYour playlists: ")
    for index in range(len(playlists)):
        print("{index: <4} {name}".format(index=index, name=playlists[index]['name']))

    is_selected = False
    while not is_selected:
        selected = int(input("\nNow type the playlist you would like to sort by number: ".strip()) or -1)
        if 0 <= selected < len(playlists): 
            is_selected = input("You are sorting list '{}', type 'y' if you want to continue.".format(playlists[selected]['name'])).lower() == "y"

    return playlists[selected]


# Function that's for getting a dictionary of all user playlists. 
def get_playlist_tracks(sp, playlist_id):
    tracks = []
    offset = 0
    track_position = 0
    while True:

        # Get user's playlists.
        results = sp.playlist_tracks(playlist_id=playlist_id, fields="total,items(track(id,uri,name,artists(name)))", limit=50, offset=offset)
        for track in [item['track'] for item in results['items']]:
            track['track_position'] = track_position
            track['artists'] = [artist['name'] for artist in track['artists']]
            track_position += 1
            tracks.append(track)

        # Make sure we're looping until we've got everything.
        if (offset + 50) > results['total']:
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
SKIP_TRACK = 0
REPLACE_TRACK = 1
AVERAGE_TRACK = 2
def ask_track_operation():
    print("\nIf the bpm is already known, what do you want to do?")
    print("{}) Use the known bpm and skip the song".format(SKIP_TRACK))
    print("{}) Replace the previously noted bpm".format(REPLACE_TRACK))
    print("{}) Average with the previously noted bpm".format(AVERAGE_TRACK))
    while True:
        answer = int(input("Answer (0): ") or 0)
        if 0 <= answer <= 2: return answer

# Uses spotipy's function to set the right order in a playlist. Preserves added_by_date. 
def sort_playlist_based_on_tracks(sp, user_id, playlist, tracks = []):

    track_ids = [track['id'] for track in tracks]

    for offset in range(ceil(len(track_ids)/100)):
        sp.user_playlist_remove_all_occurrences_of_tracks(user=user_id, playlist_id=playlist['id'], tracks=track_ids[offset*100:offset*100+100], snapshot_id=playlist['snapshot_id'])
    
    for offset in range(ceil(len(track_ids)/100)):
        sp.user_playlist_add_tracks(user=user_id, playlist_id=playlist['id'], tracks=track_ids[offset*100:offset*100+100])

    # Sorting algorithm that would have worked if I had more time ...
    # for i in range(len(tracks)-1, -1, -1):
    #     print("moving {name} from pos {old} to pos {new}.".format(name=tracks[i]['name'], old=tracks[i]['track_position'], new=i))
    #     sp.user_playlist_reorder_tracks(user_id, playlist['id'], snapshot_id=playlist['snapshot_id'], range_start=tracks[i]['track_position'], insert_before=i)
    #     if i % 5 == 0:
    #         print("Giving spotify a rest...")
    #         time.sleep(5)
    print("Sorting 100% done!")


# =========================== Non Function Code ============================ #

# Setting up the Spotify-client using online authentication. We require a lot of credentials. :')
print("Hi! We're going to log you in now.")
time.sleep(2)
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
playlist = select_playlist(sp)
user_id = sp.current_user()['id']
tracks = get_playlist_tracks(sp, playlist_id = playlist['id'])

# Ask for the amount of taps, amount of skipped seconds, operation per track and automatic play option.
print("Be aware that this tool will reset the added-by-date in your spotify list. Continue only if you don't mind.")
taps = int(input("Taps to enter per song (8): ") or 8)
standard_skip = int(input("Seconds headstart in songs (30): ") or 30)*1000
track_operation = ask_track_operation()
automated_music = ask_automated_music()
if automated_music: device_id = select_user_device(sp)

# Open bpm database (local cache).
bpm_database = open_bpm_cache()

# Start analysing the songs. This is in a try_catch loop, so we don't lose analysed songs.
print("\nWe're starting the sorting of songs now.")
# try: 
if True:
    
    # Loop over the index of all tracks in the playlist.
    for track_index in range(len(tracks)):

        # Get current track based on index, get the known bpm if it exists.
        track = tracks[track_index]
        track_bpm_known = (bpm_database and track['id'] in bpm_database and 'bpm' in bpm_database[track['id']])

        # If we already have the track information and operation is to skip it, skip it.
        if track_bpm_known and track_operation == SKIP_TRACK:
            tracks[track_index]['bpm'] = bpm_database[track['id']]['bpm']
            continue

        # Sleep a bit to give the user a bit of rest.
        time.sleep(0.5)
        print("{cur}/{total} Analysing {name} by {artist}".format(cur=track_index, total=len(tracks), name=track['name'], artist=", ".join(track['artists'])))
        
        # Play music if user requested it.
        if automated_music: 
            sp.start_playback(device_id=device_id, uris=[track['uri']])
            sp.seek_track(position_ms=standard_skip, device_id=device_id)

        # Determining the bpm
        bpm = determine_bpm(taps)
        print("You determined this song on {} bpm.".format(bpm))

        # Averaging this bpm with the one already noted, if the user requested so.
        if track_bpm_known and track_operation == AVERAGE_TRACK:
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
    sort_playlist_based_on_tracks(sp, user_id=user_id, playlist=playlist, tracks=tracks)

# Catch exceptions.
# except BaseException as e: 
#     print(str(e))
#     print("Something went wrong while analysing. Songs until now have been saved. Nothing is sorted.")

# Write the user's work to the disk.
with open(CACHE_FILE, "w") as json_file:
    json_file.write(json.dumps(bpm_database))

# We're done here folks!
print("===== All {} tracks finished processing! ====".format(len(tracks)))