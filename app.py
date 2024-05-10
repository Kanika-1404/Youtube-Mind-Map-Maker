from flask import Flask, render_template, request, redirect, url_for
from os import path
from pytube import YouTube
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import speech_recognition as sr
from youtube_transcript_api import YouTubeTranscriptApi as yta
import re
import spacy
from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest
from datetime import datetime
import requests

app = Flask(__name__)

# Function to download video from YouTube
def download_video(url, output_path="."):
    yt = YouTube(url)
    video_stream = yt.streams.get_highest_resolution()
    video_filename = video_stream.download(output_path=output_path)
    return video_filename

# Function to extract audio from video
def extract_audio(video_filename, output_filename):
    video = VideoFileClip(video_filename)
    audio = video.audio
    audio.write_audiofile(output_filename)

# Function to convert audio to WAV format
def convert_to_wav(mp3_filename, wav_filename):
    mp3_file = AudioSegment.from_mp3(mp3_filename)
    mp3_file.export(wav_filename, format="wav")

# Function to get video ID from YouTube URL
def get_video_id(url):
    video_id = None
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    if match:
        video_id = match.group(1)
    return video_id

# Function to generate transcript from YouTube video URL
def generate_transcript_from_url(video_url):
    video_id = get_video_id(video_url)
    if video_id:
        try:
            data = yta.get_transcript(video_id)
            transcript = ''
            for value in data:
                for key, val in value.items():
                    if key == 'text':
                        transcript += val + ' '  # Append the text without the timestamp
            return transcript
        except Exception as e:
            return None
    else:
        return None

# Function to summarize transcript
def summarize_transcript(text, per):
    nlp = spacy.load('en_core_web_sm')
    doc = nlp(text)
    sentence_tokens = [sent.text for sent in doc.sents]
    word_frequencies = {}
    for word in doc:
        if word.text.lower() not in STOP_WORDS:
            if word.text.lower() not in punctuation:
                if word.text not in word_frequencies.keys():
                    word_frequencies[word.text] = 1
                else:
                    word_frequencies[word.text] += 1
    max_frequency = max(word_frequencies.values())
    for word in word_frequencies.keys():
        word_frequencies[word] = word_frequencies[word] / max_frequency
    sentence_scores = {}
    for sent in sentence_tokens:
        sent_doc = nlp(sent)
        for word in sent_doc:
            if word.text.lower() in word_frequencies.keys():
                if sent not in sentence_scores.keys():
                    sentence_scores[sent] = word_frequencies[word.text.lower()]
                else:
                    sentence_scores[sent] += word_frequencies[word.text.lower()]
    select_length = int(len(sentence_tokens) * per)
    summary = nlargest(select_length, sentence_scores, key=sentence_scores.get)
    final_summary = [f"[{datetime.now().strftime('%H:%M:%S')}] {sent}" for sent in summary]
    summary = '\n'.join(final_summary)
    return summary


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return render_template('video.html')

@app.route('/download_video', methods=['POST'])
def download_video_route():
    video_url = request.form['video_url']
    try:
        video_filename = download_video(video_url)
        message = f"Video '{video_filename}' has been downloaded successfully."
    except Exception as e:
        message = f"Error: {str(e)}"
    return render_template('video.html', message=message)

@app.route('/audio')
def audio():
    return render_template('audio.html')

@app.route('/extract_audio', methods=['POST'])
def extract_audio_route():
    video_url = request.form['video_url']
    try:
        video_filename = download_video(video_url)
        audio_filename = "audio.mp3"
        extract_audio(video_filename, audio_filename)
        message = f"Audio has been extracted and saved as '{audio_filename}'."
    except Exception as e:
        message = f"Error: {str(e)}"
    return render_template('audio.html', message=message)

@app.route('/text')
def text():
    return render_template('text.html')

@app.route('/textextraction', methods=['POST'])
def extract_text():
    video_url = request.form['video_url']
    transcript = generate_transcript_from_url(video_url)
    if transcript:
        extracted_text = summarize_transcript(transcript, 0.3)  # Adjust the per parameter as needed
        if extracted_text:
            return render_template('extracted_text.html', extracted_text=extracted_text)
        else:
            return "Failed to generate summary."
    else:
        return "Failed to generate transcript."



@app.route('/summarizer')
def summarizer():
    return render_template('summary.html')

# Route to summarize the extracted transcript
@app.route('/summarizetext', methods=['POST'])
def summarize_text():
    video_url = request.form['video_url']
    transcript = generate_transcript_from_url(video_url)
    if transcript:
        summary = summarize_transcript(transcript, 0.2)  # Adjust the per parameter as needed
        if summary:
            return render_template('summarized_text.html', summary=summary)
        else:
            return "Failed to generate summary."
    else:
        return "Failed to generate transcript."
    

# Mindmap route

@app.route('/mindmap')
def mindmap():
    return render_template('mindmap.html')


@app.route('/mindmapmake', methods=['POST'])
def make_mindmap():
    video_url = request.form['video_url']
    
    # Generate transcript from the video URL
    transcript = generate_transcript_from_url(video_url)
    if transcript:
        # Summarize the transcript
        extracted_text = summarize_transcript(transcript, 0.3)  # Adjust the parameter as needed
        if extracted_text:
            # Request mind map generation using ChatGPT API
            url = "https://chatgpt-42.p.rapidapi.com/gpt4"
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": "Please make a mind map of the following text:\n\n" + extracted_text
                    }
                ],
                "web_access": False
            }
            headers = {
                "content-type": "application/json",
                "X-RapidAPI-Key": "cbf1c8acbfmsha652024aa328175p1e7b6djsn0a11b44469b7",
                "X-RapidAPI-Host": "chatgpt-42.p.rapidapi.com"
            }
            response = requests.post(url, json=payload, headers=headers)
            
            # Check if request was successful
            if response.status_code == 200:
                # Extract the mind map
                mind_map = response.json().get("result", "")
                
                # Make headings bold
                mind_map = mind_map.replace('<h1>', '<b>').replace('</h1>', '</b>')
                
                # Render the map.html template with the mind map data
                return render_template('map.html', mind_map=mind_map.replace('\n', '<br>'))
            else:
                return "Failed to generate mind map."
        else:
            return "Failed to generate summary."
    else:
        return "Failed to generate transcript."

    
if __name__ == "__main__":
    app.run(debug=True)