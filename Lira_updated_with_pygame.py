import speech_recognition as sr
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import wolframalpha
import wikipedia
import datetime
from dotenv import load_dotenv
import os
import pvporcupine
import pyaudio
import numpy as np
from gtts import gTTS
from pydub import AudioSegment
import pygame
import time
import threading

# Load environment variables from .env file
load_dotenv()

# Initialize global flag for stopping speech
stop_speaking_flag = False

# Initialize Spotify client globally
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="user-read-playback-state,user-modify-playback-state",
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI")
))

def stop_speaking():
    """Stop ongoing speech."""
    global stop_speaking_flag
    stop_speaking_flag = True

file_access_event = threading.Event()
file_access_event.set()

def play_chime():
    """Play a chime sound when the wake word is detected."""
    chime_filename = "chime.wav"
    
    if not os.path.exists(chime_filename):
        print("Chime file not found!")
        return
    
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(chime_filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        print("Chime played successfully.")
    except Exception as e:
        print(f"An error occurred while playing the chime: {e}")
    finally:
        pygame.mixer.quit()

def speak(text):
    """Convert text to speech and play it."""
    global stop_speaking_flag
    stop_speaking_flag = False
    mp3_filename = "output.mp3"
    wav_filename = "output.wav"
    
    # Wait until the file is not in use
    file_access_event.wait()
    file_access_event.clear()

    # Delete old files if they exist
    if os.path.exists(mp3_filename):
        os.remove(mp3_filename)
    if os.path.exists(wav_filename):
        os.remove(wav_filename)
    
    # Save the TTS output as an MP3 file
    tts = gTTS(text=text, lang='en')
    tts.save(mp3_filename)
    print("TTS file saved as output.mp3")
    
    # Convert the MP3 file to WAV format
    sound = AudioSegment.from_mp3(mp3_filename)
    sound.export(wav_filename, format="wav")
    print("File converted to output.wav")

    try:
        # Initialize pygame mixer and play the WAV file
        pygame.mixer.init()
        pygame.mixer.music.load(wav_filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and not stop_speaking_flag:
            time.sleep(0.1)
        print("Finished playing the WAV file")
    except Exception as e:
        print(f"An error occurred during playback: {e}")
    finally:
        pygame.mixer.quit()
        time.sleep(0.5)
        file_access_event.set()

def listen():
    """Listen for voice commands and convert them to text."""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 2500  # Lower the energy threshold
    recognizer.pause_threshold = 0.5    # Adjust pause threshold to reduce delay

    with sr.Microphone() as source:
        print("\nListening...")
        audio = recognizer.listen(source)  # Removed the timeout parameter to allow indefinite listening
        try:
            print("Recognizing...")
            command = recognizer.recognize_google(audio)
            print(f"You said: {command}\n")
            return command.lower()
        except sr.UnknownValueError:
            speak("Sorry, I didn't catch that.")
            return ""
        except sr.RequestError:
            speak("Sorry, I'm having trouble connecting to the service.")
            return ""

def wake_word_listener():
    """Use Porcupine to detect the wake word 'Hey Lira'."""
    porcupine = None
    pa = None
    audio_stream = None

    try:
        porcupine = pvporcupine.create(
            access_key='FVYSqJsZV9N12ey8c8OlJnp5Dj/KGCBxzLTM/GwY9nXVT1ABzSwwrQ==',  # Replace with your actual access key
            keyword_paths=['Hey-Lira_en_windows_v3_0_0.ppn']  # Path to your "Hey Lira" .ppn file
        )

        pa = pyaudio.PyAudio()

        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length)

        while True:
            pcm = audio_stream.read(porcupine.frame_length)
            pcm = np.frombuffer(pcm, dtype=np.int16)

            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                print("Wake word detected!")
                play_chime()  # Play the chime when the wake word is detected
                return True

    finally:
        if audio_stream is not None:
            audio_stream.close()

        if pa is not None:
            pa.terminate()

        if porcupine is not None:
            porcupine.delete()

def calculate(query):
    """Use Wolfram Alpha to compute the answer to a query."""
    app_id = os.getenv("WOLFRAMALPHA_APP_ID")
    client = wolframalpha.Client(app_id)
    try:
        res = client.query(query)
        answer = next(res.results).text
        speak(f"The answer is {answer}")
    except Exception:
        speak("Sorry, I couldn't compute that.")

def tell_time():
    """Tells the current time."""
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    speak(f"The time is {current_time}.")

def tell_date():
    """Tells the current date."""
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    speak(f"Today is {current_date}.")

# Define the prioritized list of device names and IDs
priority_devices = {
    "device 1": {"names": ["GUSLAPTOP", "device 1", "device one"], "id": "e5574be83d300a9e1505b99eb8b10d73f500bc11"},
    "device 2": {"names": ["Gus's Echo", "device two", "device 2", "device too", "device to"], "id": "917d9c85-bc92-45d4-938c-00fb043ca2b0_amzn_1"},
    "device 3": {"names": ["iPhone","device three","device 3"], "id": "0ee736140798d3f07f4b9170689b989730ad1b91"}
}

restart_phrases = [
    "restart", "restart song", "replay", "play again", "rewind", "start again", "start over", "rewind",'restar']

volume_increase_phrases = [
    "increase","increase volume",'crank it','crank it up','turn it up','louder', 'volume up']

volume_decrease_phrases = [
    "decrease", "decrease volume", "turn it down", "lower it", "quieter", "turn it off","shush",'volume down']

skip_phrases = [ 
    "skip","next"]

# Initialize global variable for current device ID
current_device_id = None

def find_available_device(device_list):
    """Find an active or available Spotify device from the list."""
    for device in device_list:
        if device.get('is_active'):
            return device['id']
    return None  # If no active device is found, return None

def switch_device(device_id):
    """Switch Spotify playback to a specific device."""
    global current_device_id
    current_device_id = device_id
    try:
        sp.transfer_playback(device_id=device_id, force_play=True)
        speak(f"Switched playback to the selected device.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "switch devices")

def clear_queue():
    """Clear the current queue."""
    try:
        playback_info = sp.current_playback()
        if playback_info:
            sp.next_track()
            sp.pause_playback()
            speak("Cleared the previous queue.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "clear the queue")

def skip_track():
    """Skip to the next track in the Spotify playback."""
    try:
        sp.next_track(device_id=current_device_id)
        speak("Skipped to the next track.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "skip the track on Spotify")

def pause_spotify():
    """Pause the current Spotify playback."""
    try:
        sp.pause_playback(device_id=current_device_id)
        speak("Playback paused on Spotify.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "pause the playback on Spotify")

def resume_spotify():
    """Resume the current Spotify playback."""
    try:
        sp.start_playback(device_id=current_device_id)
        speak("Resuming Spotify playback.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "resume playback on Spotify")

def change_volume(action):
    """Increase or decrease Spotify volume."""
    try:
        current_volume = sp.current_playback()['device']['volume_percent']
        if action == "up":
            new_volume = min(current_volume + 10, 100)  # Increase volume by 10%, max at 100%
        elif action == "down":
            new_volume = max(current_volume - 10, 0)  # Decrease volume by 10%, min at 0%
        sp.volume(new_volume, device_id=current_device_id)
        speak(f"Volume set to {new_volume} percent.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "change the volume on Spotify")

def get_current_track_uri():
    """Fetch the URI of the currently playing track."""
    playback_info = sp.current_playback()
    if playback_info and playback_info['is_playing'] and playback_info['item']:
        return playback_info['item']['uri']
    else:
        speak("No track is currently playing.")
        return None

def queue_tracks(tracks):
    """Queue a list of tracks and print them to the console."""
    if tracks:
        for track in tracks:
            sp.add_to_queue(track['uri'], device_id=current_device_id)
            print(f"Queued: {track['name']} by {track['artist']}")
        speak("Queued similar tracks.")
    else:
        speak("No similar tracks found.")

def get_similar_tracks(track_uri):
    """Fetch recommendations for similar tracks based on the current track."""
    try:
        recommendations = sp.recommendations(seed_tracks=[track_uri], limit=5)
        return [{'uri': track['uri'], 'name': track['name'], 'artist': track['artists'][0]['name']} for track in recommendations['tracks']]
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "get recommendations")
        return []

def autoplay():
    """Queue similar songs after the current track ends."""
    try:
        current_track_uri = get_current_track_uri()
        if current_track_uri:
            queue_tracks(get_similar_tracks(current_track_uri))
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "set up autoplay")

def restart_song():
    """Restart the current song from the beginning."""
    try:
        sp.seek_track(0, device_id=current_device_id)
        speak("Restarted the current song.")
    except spotipy.exceptions.SpotifyException as e:
        handle_spotify_error(e, "restart the song")

def check_playback():
    """Check the playback status and queue similar tracks if needed."""
    while True:
        try:
            playback_info = sp.current_playback()
            if playback_info and playback_info['is_playing']:
                remaining_time = playback_info['item']['duration_ms'] - playback_info['progress_ms']
                if remaining_time < 30000:  # Last 30 seconds
                    print("Less than 30 seconds remaining. Queueing similar tracks.")
                    autoplay()
            time.sleep(10)  # Check every 10 seconds
        except spotipy.exceptions.SpotifyException as e:
            handle_spotify_error(e, "check playback")
            time.sleep(60)  # Wait before retrying in case of error
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            time.sleep(60)  # Wait before retrying in case of error

def handle_spotify_error(exception, action):
    """Handle Spotify exceptions with a generic message."""
    speak(f"Sorry, I couldn't {action} on Spotify.")
    print(f"Spotify Error: {exception}")

def play_spotify(track_name):
    """Play a specific song on Spotify."""
    devices = sp.devices().get('devices', [])

    if not devices:
        speak("No active Spotify devices found. Please open Spotify on one of your devices and try again.")
        return

    current_device_id = devices[0]['id']

    clear_queue()

    # Search specifically for a track and play the first result
    results = sp.search(q=track_name, type='track', limit=1)
    tracks = results.get('tracks', {}).get('items', [])
    if not tracks:
        speak(f"Sorry, I couldn't find the track '{track_name}' on Spotify.")
        return

    track_uri = tracks[0]['uri']
    try:
        sp.start_playback(device_id=current_device_id, uris=[track_uri])
        speak(f"Now playing '{track_name}' on Spotify.")
    except spotipy.exceptions.SpotifyException as e:
        speak(f"Sorry, I couldn't play the track on Spotify.")
        print(f"Spotify Error: {e}")

def play_playlist(playlist_name):
    """Play a specific playlist on Spotify."""
    devices = sp.devices().get('devices', [])

    if not devices:
        speak("No active Spotify devices found. Please open Spotify on one of your devices and try again.")
        return

    current_device_id = find_available_device(devices) or devices[0]['id']

    # Search for the playlist and play the first result
    results = sp.search(q=playlist_name, type='playlist', limit=1)
    playlists = results.get('playlists', {}).get('items', [])
    
    if playlists:
        playlist_uri = playlists[0]['uri']  # Select the first playlist returned
        try:
            sp.start_playback(device_id=current_device_id, context_uri=playlist_uri)
            speak(f"Playing playlist '{playlist_name}' on Spotify.")
        except spotipy.exceptions.SpotifyException as e:
            speak(f"Sorry, I couldn't play the playlist on Spotify.")
            print(f"Spotify Error: {e}")
    else:
        speak(f"Sorry, I couldn't find the playlist '{playlist_name}' on Spotify.")

def process_command(command):
    """Process and execute the user's command."""
    global stop_speaking

    if not command:
        return

    # Handle device switching
    for device_key, device_info in priority_devices.items():
        if any(name.lower() in command.lower() for name in device_info['names']):
            switch_device(device_info['id'])
            return

    if 'stop' in command:
        stop_speaking()
        pause_spotify()
        return  # Stop further processing and return to wake word listener

    if any(phrase in command.lower() for phrase in restart_phrases):
        restart_song()
        return
        
    if 'clear' in command:
        clear_queue()
        return

    if 'play the playlist' in command.lower():
        playlist_name = command.lower().replace('play the playlist', '').strip()
        play_playlist(playlist_name)
        return
    
    if 'play' in command.lower() and 'playlist' not in command.lower():
        track_name = command.lower().replace('play', '').replace('on spotify', '').strip()
        play_spotify(track_name)
        return
    
    if 'resume' in command:
        resume_spotify()

    elif any(phrase in command.lower() for phrase in skip_phrases):
        skip_track()
        return

    elif any(phrase in command.lower() for phrase in volume_increase_phrases):
        change_volume("up")
        return

    elif any(phrase in command.lower() for phrase in volume_decrease_phrases):
        change_volume("down")
        return

    elif 'what is' in command or 'calculate' in command or 'solve' in command:
        query = command.replace('what is', '').replace('calculate', '').replace('solve', '').strip()
        if query:
            calculate(query)
        else:
            speak("Please specify what you want me to calculate.")
    
    elif 'time' in command:
        tell_time()
    
    elif 'date' in command or 'day' in command:
        tell_date()
    
    elif 'exit' in command or 'quit' in command or 'stop' in command:
        speak("Goodbye! Have a nice day.")
        exit()
    
    else:
        speak("I'm sorry, I didn't get that.")



def main():
    """Main function to run the assistant."""
    speak("Hello, I am Lira")

    playback_thread = threading.Thread(target=check_playback, daemon=True)
    playback_thread.start()

    while True:
        if wake_word_listener():
            command = listen()
            process_command(command)

if __name__ == "__main__":
    main()
