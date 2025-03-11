import os
import shutil
import subprocess
import yt_dlp
import whisper
from glob import glob
import random
import string
import pysubs2
import torch
import requests
import json
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider 
from dotenv import load_dotenv
from subtitle_design import apply_design  # `subtitle_design.py` থেকে ডিজাইন ফাংশন ইমপোর্ট করা হচ্ছে
from azure_prompt import generate_output_from_azure  # Azure AI এর ফাংশনটি ইমপোর্ট করা হচ্ছে
from metadata_updater import set_file_properties
from metadata_updater import process_video_metadata
from ai_voice_generator import transcribe_and_generate_ai_voice  # AI ভয়েস ফাংশন ইমপোর্ট করা হচ্ছে
import time
from face_footage_handler import FaceFootageHandler
import math  # যোগ করুন যদি আগে না থাকে
from subtitle_design import generate_subtitles_karaoke_chunked

# # voice_cloning.py ফাইল ইমপোর্ট করুন
# from voice_cloning import generate_cloned_voice_from_transcript

load_dotenv()  # এটি আপনার .env ফাইল থেকে পরিবেশ ভেরিয়েবলগুলো লোড করবে


# Azure OpenAI API কনফিগারেশন
endpoint = os.getenv("ENDPOINT_URL", "https://et1.openai.azure.com/")  
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o")  

# Initialize Azure OpenAI Service client with Entra ID authentication
token_provider = get_bearer_token_provider(  
    DefaultAzureCredential(),  
    "https://cognitiveservices.azure.com/.default"  
)  

client = AzureOpenAI(  
    azure_endpoint=endpoint,  
    azure_ad_token_provider=token_provider,  
    api_version="2024-05-01-preview",  
)

# 🔹 কনফিগারেশন
BASE_PATH = "D:/video_project/"
OLD_AUDIO_FOLDER = "D:/video_project/old_audio"
YOUTUBE_URL_FILE = os.path.join(BASE_PATH, "youtube_urls.txt")
YOUTUBE_SHORTS_URL_FILE = os.path.join(BASE_PATH, "youtube_shorts_urls.txt")
# AI ভয়েস ভিডিও URL ফাইল
YOUTUBE_AI_VOICE_SHORTS_URL_FILE = os.path.join(BASE_PATH, "youtube_ai_voice_shorts_urls.txt")
YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE = os.path.join(BASE_PATH, "youtube_ai_voice_long_video_urls.txt")

AUDIO_FOLDER = os.path.join(BASE_PATH, "audio_files")
STOCK_VIDEO = os.path.join(BASE_PATH, "stock_video.mp4")  # ফলব্যাক হিসেবে
OUTPUT_FOLDER = os.path.join(BASE_PATH, "output_videos")
SHORTS_FOLDER = os.path.join(OUTPUT_FOLDER, "shorts")
TEMP_FOLDER = os.path.join(BASE_PATH, "temp_output")
SHORTS_STOCK_VIDEOS_FOLDER = os.path.join(BASE_PATH, "shorts_stock_videos")
STOCK_VIDEOS_FOLDER = os.path.join(BASE_PATH, "stock_videos")
BACKGROUND_MUSIC_FOLDER = os.path.join(BASE_PATH, "background_music")
# কনফিগারেশনে যোগ করুন
CLONE_AUDIO_FOLDER = os.path.join(BASE_PATH, "clone_audio")
YOUTUBE_CLONE_SHORTS_URL_FILE = os.path.join(BASE_PATH, "youtube_clone_shorts.txt")



# 🔹 ফেস ফুটেজ ফোল্ডার কনফিগারেশন
REAL_FOOTAGE_SHORTS_FOLDER = os.path.join(BASE_PATH, "real_footage_shorts")
REAL_FOOTAGE_LONG_FOLDER = os.path.join(BASE_PATH, "real_footage_long")
YOUTUBE_SHORTS_WITH_FACE_URL_FILE = os.path.join(BASE_PATH, "youtube_shorts_with_5_sec_with_face.txt")
YOUTUBE_LONG_WITH_FACE_URL_FILE = os.path.join(BASE_PATH, "youtube_long_with_5_sec_with_face.txt")
YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE = os.path.join(BASE_PATH, "youtube_shorts_with_5_sec_with_face_ai.txt")
YOUTUBE_LONG_WITH_FACE_AI_URL_FILE = os.path.join(BASE_PATH, "youtube_long_with_5_sec_with_face_ai.txt")

# লগ ফাইলের পাথ
LOG_FILE = os.path.join(BASE_PATH, "already_done.txt")

# 🔹 Ensure output directories exist
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(SHORTS_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(SHORTS_STOCK_VIDEOS_FOLDER, exist_ok=True)
# ফোল্ডার গুলি নিশ্চিত করুন
os.makedirs(REAL_FOOTAGE_SHORTS_FOLDER, exist_ok=True)
os.makedirs(REAL_FOOTAGE_LONG_FOLDER, exist_ok=True)

# FaceFootageHandler ইনিশিয়ালাইজ করুন
face_handler = FaceFootageHandler(BASE_PATH)

os.makedirs(CLONE_AUDIO_FOLDER, exist_ok=True)

# ফাইল নাম সেনিটাইজ করার ফাংশন
def sanitize_filename(filename):
    """
    ফাইল নাম থেকে বিশেষ অক্ষরগুলো রিমুভ করে শুধুমাত্র সেফ ক্যারেক্টার রাখে।
    
    Args:
        filename (str): অরিজিনাল ফাইলনাম
        
    Returns:
        tuple: (sanitized_name, original_name) - সেনিটাইজ করা নাম এবং অরিজিনাল নাম
    """
    # অরিজিনাল নাম সংরক্ষণ করুন
    original_name = filename
    
    # এক্সটেনশন আলাদা করুন
    base_name, extension = os.path.splitext(filename)
    
    # বিশেষ ক্যারেক্টার রিমুভ করুন এবং স্পেস আন্ডারস্কোর দিয়ে প্রতিস্থাপন করুন
    sanitized_base = re.sub(r'[^\w\s-]', '', base_name)
    sanitized_base = re.sub(r'[\s]+', '_', sanitized_base)
    
    # খুব লম্বা নাম হলে সেটি শর্ট করুন
    if len(sanitized_base) > 50:
        sanitized_base = sanitized_base[:50]
    
    # সেনিটাইজ করা নাম ফিরিয়ে দিন
    sanitized_name = sanitized_base + extension
    
    return sanitized_name, original_name


# ফাইল নাম ম্যাপিং এর জন্য ডিকশনারি
filename_mapping = {}

def map_filename(original_path, sanitized_path):
    """
    অরিজিনাল ফাইল পাথ এবং সেনিটাইজ করা ফাইল পাথের ম্যাপিং রাখে।
    
    Args:
        original_path (str): অরিজিনাল ফাইল পাথ
        sanitized_path (str): সেনিটাইজ করা ফাইল পাথ
    """
    filename_mapping[sanitized_path] = original_path
    
def get_original_filename(sanitized_path):
    """
    সেনিটাইজ করা ফাইল পাথ থেকে অরিজিনাল ফাইল পাথ পায়।
    
    Args:
        sanitized_path (str): সেনিটাইজ করা ফাইল পাথ
        
    Returns:
        str: অরিজিনাল ফাইল পাথ, যদি পাওয়া যায়; অন্যথায় সেনিটাইজ করা পাথ
    """
    return filename_mapping.get(sanitized_path, sanitized_path)

def get_original_basename(sanitized_path):
    """
    সেনিটাইজ করা ফাইল পাথ থেকে অরিজিনাল ফাইল নাম (বেসনাম) পায়।
    
    Args:
        sanitized_path (str): সেনিটাইজ করা ফাইল পাথ
        
    Returns:
        str: অরিজিনাল ফাইলের বেসনাম, যদি পাওয়া যায়; অন্যথায় সেনিটাইজ করা বেসনাম
    """
    original_path = get_original_filename(sanitized_path)
    return os.path.splitext(os.path.basename(original_path))[0]


def process_single_url(url, url_file):
    """
    একটি URL প্রসেস করার পূর্ণাঙ্গ পদ্ধতি
    """
    processed_urls = load_processed_urls()
    
    # URL ইতিমধ্যে প্রসেস করা হয়েছে কিনা চেক করুন
    if url in processed_urls:
        print(f"⏩ URL ইতিমধ্যে প্রসেস করা হয়েছে: {url}")
        return False
    
    try:
        # URL ডাউনলোড এবং প্রসেসিং
        temp_url_file = os.path.join(BASE_PATH, f"temp_url_{int(time.time())}.txt")
        with open(temp_url_file, 'w', encoding='utf-8') as f:
            f.write(url)
        
        # ডাউনলোড এবং প্রসেস
        audio_files = download_youtube_audio(temp_url_file)
        
        if audio_files:
            # সফল হলে URL লগ ফাইলে যোগ করুন
            save_processed_url(url)
            
            # টেম্পরারি ফাইল মুছে দিন
            os.remove(temp_url_file)
            
            # URL মূল ফাইল থেকে মুছে দিন
            remove_url_from_file(url, url_file)
            
            return True
        else:
            print(f"❌ URL প্রসেসিংয়ে ব্যর্থ: {url}")
            return False
    
    except Exception as e:
        print(f"❌ URL প্রসেসিংয়ে ত্রুটি: {url} - {e}")
        return False


def process_long_audio_in_chunks(audio_file, audio_temp_folder, use_ai_voice=False):
    """
    দীর্ঘ অডিও ফাইলকে চাঙ্কে ভাগ করে, প্রতিটি চাঙ্কের ব্যাকগ্রাউন্ড মিউজিক রিমুভ করে 
    এবং তারপর সব চাঙ্ক একত্রিত করে একটি পূর্ণাঙ্গ ফিল্টার করা অডিও ফাইল তৈরি করে।
    আপডেটেড: বিশেষ পদ্ধতিতে এরর হ্যান্ডলিং ও রিকভারি যোগ করা হয়েছে
    """
    audio_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # অডিও দৈর্ঘ্য চেক করুন
    try:
        duration_cmd = f'ffprobe -i "{audio_file}" -show_entries format=duration -v quiet -of csv="p=0"'
        audio_duration = float(subprocess.check_output(duration_cmd, shell=True).decode().strip())
        print(f"📊 Audio duration: {audio_duration:.2f}s ({audio_duration/60:.2f} minutes)")
        
        # 10 মিনিটের কম হলে সরাসরি প্রসেস করুন
        if audio_duration <= 600:  # 10 minutes in seconds
            print(f"✅ Audio is shorter than 10 minutes, processing directly")
            filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
            remove_background_music(audio_file, filtered_audio, audio_temp_folder)
            
            # যদি AI ভয়েস ব্যবহার করতে হয়
            if use_ai_voice:
                print("🎙️ Transcribing audio for AI voice generation...")
                transcript = transcribe_audio(filtered_audio)
                
                if transcript:
                    ai_voice_file = transcribe_and_generate_ai_voice(transcript, audio_name, audio_temp_folder)
                    
                    if ai_voice_file and os.path.exists(ai_voice_file):
                        print(f"✅ Using AI voice: {ai_voice_file}")
                        return ai_voice_file
                    
            return filtered_audio
        
        # এখানে অডিও চাঙ্কিং করা হবে
        print("🔄 Audio is longer than 10 minutes, splitting into chunks for processing...")
        
        # চাঙ্ক ফোল্ডার তৈরি করুন
        chunks_folder = os.path.join(audio_temp_folder, "chunks")
        os.makedirs(chunks_folder, exist_ok=True)
        
        # পূর্বের চাঙ্ক সাইজ 300 সেকেন্ড ছিল, এটা আরও কম করে বেশি রিলায়েবল করা হচ্ছে
        chunk_size = 240  # 4 মিনিট (আগে 5 মিনিট ছিল)
        
        # চাঙ্ক সংখ্যা গণনা
        num_chunks = math.ceil(audio_duration / chunk_size)
        print(f"🔪 Splitting audio into {num_chunks} chunks of {chunk_size/60:.1f} minutes each")
        
        # প্রতিটি চাঙ্ক তৈরি এবং প্রসেস করুন
        filtered_chunks = []
        
        for i in range(num_chunks):
            start_time = i * chunk_size
            # শেষ চাঙ্কের জন্য যদি বাকি সময় কম থাকে
            if i == num_chunks - 1:
                duration = audio_duration - start_time
            else:
                duration = chunk_size
            
            # চাঙ্ক ফাইল পাথ
            chunk_file = os.path.join(chunks_folder, f"chunk_{i+1}.mp3")
            
            # ffmpeg দিয়ে চাঙ্ক তৈরি - সর্বোচ্চ 3 বার চেষ্টা করবে
            max_attempts = 3
            chunk_success = False
            
            for attempt in range(max_attempts):
                try:
                    chunk_cmd = f'ffmpeg -i "{audio_file}" -ss {start_time} -t {duration} -c:a libmp3lame -q:a 2 "{chunk_file}" -y'
                    subprocess.run(chunk_cmd, shell=True, timeout=300)  # 5 মিনিট টাইমআউট
                    
                    if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 1000:  # কমপক্ষে 1KB
                        chunk_success = True
                        print(f"✅ Created chunk {i+1}/{num_chunks}: {chunk_file} (Attempt {attempt+1})")
                        break
                    else:
                        print(f"⚠️ Chunk file created but may be invalid: {chunk_file} (Attempt {attempt+1})")
                except Exception as e:
                    print(f"⚠️ Error creating chunk {i+1}, attempt {attempt+1}: {e}")
            
            if not chunk_success:
                print(f"❌ Failed to create chunk {i+1} after {max_attempts} attempts, skipping")
                continue
            
            # প্রতিটি চাঙ্কের ব্যাকগ্রাউন্ড মিউজিক রিমুভ করুন
            filtered_chunk = os.path.join(chunks_folder, f"chunk_{i+1}_filtered.wav")
            print(f"🔊 Removing background from chunk {i+1}/{num_chunks}")
            
            # ব্যাকগ্রাউন্ড রিমুভাল - সর্বোচ্চ 2 বার চেষ্টা করবে
            filter_success = False
            for attempt in range(2):
                try:
                    remove_background_music(chunk_file, filtered_chunk, chunks_folder)
                    
                    if os.path.exists(filtered_chunk) and os.path.getsize(filtered_chunk) > 1000:  # কমপক্ষে 1KB
                        filtered_chunks.append(filtered_chunk)
                        print(f"✅ Processed chunk {i+1}/{num_chunks} (Attempt {attempt+1})")
                        filter_success = True
                        break
                except Exception as e:
                    print(f"⚠️ Error processing chunk {i+1}, attempt {attempt+1}: {e}")
            
            # যদি ফিল্টারিং ব্যর্থ হয়, তাহলে অরিজিনাল ফাইল ব্যবহার করুন
            if not filter_success:
                print(f"⚠️ Using original chunk without filtering for chunk {i+1}")
                # অরিজিনাল চাঙ্ক WAV ফরম্যাটে কনভার্ট করুন
                wav_chunk = os.path.join(chunks_folder, f"chunk_{i+1}_original.wav")
                try:
                    convert_cmd = f'ffmpeg -i "{chunk_file}" -c:a pcm_s16le "{wav_chunk}" -y'
                    subprocess.run(convert_cmd, shell=True)
                    if os.path.exists(wav_chunk) and os.path.getsize(wav_chunk) > 0:
                        filtered_chunks.append(wav_chunk)
                    else:
                        # এখনও ব্যর্থ হলে, অরিজিনাল MP3 রাখুন
                        filtered_chunks.append(chunk_file)
                except:
                    # কনভার্শন ব্যর্থ হলে, অরিজিনাল রাখুন
                    filtered_chunks.append(chunk_file)
        
        # যদি কোনো চাঙ্ক প্রসেস না হয়
        if not filtered_chunks:
            print("❌ No chunks were successfully processed")
            print("⚠️ Falling back to original audio file")
            # ফলব্যাক হিসেবে অরিজিনাল অডিও রিটার্ন করুন
            return audio_file
        
        # এখন সব ফিল্টার করা চাঙ্ক একত্রিত করুন একটি সিঙ্গেল অডিও ফাইলে
        print("\n🔄 Combining all filtered chunks into a single audio file...")
        
        # ffmpeg concat ফিল্টার ব্যবহার করে চাঙ্ক একত্রিত করুন
        concat_list_file = os.path.join(chunks_folder, "concat_list.txt")
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for chunk in filtered_chunks:
                f.write(f"file '{os.path.abspath(chunk)}'\n")
        
        # ফিল্টার করা সম্পূর্ণ অডিও ফাইল
        final_filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered_combined.wav")
        
        # ffmpeg দিয়ে সব চাঙ্ক একত্রিত করুন - সর্বোচ্চ 3 বার চেষ্টা করবে
        concat_success = False
        for attempt in range(3):
            try:
                concat_cmd = f'ffmpeg -f concat -safe 0 -i "{concat_list_file}" -c:a pcm_s24le -ar 48000 "{final_filtered_audio}" -y'
                subprocess.run(concat_cmd, shell=True, timeout=600)  # 10 মিনিট টাইমআউট
                
                if os.path.exists(final_filtered_audio) and os.path.getsize(final_filtered_audio) > 10000:  # কমপক্ষে 10KB
                    concat_success = True
                    print(f"✅ Successfully combined all filtered chunks into: {final_filtered_audio} (Attempt {attempt+1})")
                    break
                else:
                    print(f"⚠️ Combined file created but may be invalid (Attempt {attempt+1})")
            except Exception as e:
                print(f"⚠️ Error combining chunks, attempt {attempt+1}: {e}")
        
        if concat_success:
            # যদি AI ভয়েস ব্যবহার করতে হয়
            if use_ai_voice:
                print("🎙️ Transcribing combined audio for AI voice generation...")
                transcript = transcribe_audio(final_filtered_audio)
                
                if transcript:
                    ai_voice_file = transcribe_and_generate_ai_voice(transcript, audio_name, audio_temp_folder)
                    
                    if ai_voice_file and os.path.exists(ai_voice_file):
                        print(f"✅ Using AI voice: {ai_voice_file}")
                        return ai_voice_file
            
            return final_filtered_audio
        else:
            print("❌ Failed to combine filtered chunks after multiple attempts")
            # যদি একত্রিত করা ব্যর্থ হয়, তবে শুধু প্রথম চাঙ্ক রিটার্ন করুন
            if filtered_chunks:
                print("⚠️ Returning only the first filtered chunk as fallback")
                return filtered_chunks[0]
            
            print("⚠️ Returning original audio file as ultimate fallback")
            return audio_file
    
    except Exception as e:
        print(f"❌ Error processing long audio in chunks: {e}")
        print("⚠️ Returning original audio file as fallback")
        return audio_file  # মূল অডিও ফাইল রিটার্ন করুন

def split_audio_into_chunks(audio_file, max_duration=600, temp_folder=None):
    """
    দীর্ঘ অডিও ফাইলকে নির্দিষ্ট দৈর্ঘ্যের চাঙ্কে ভাগ করে। 
    max_duration: প্রতি চাঙ্কের সর্বোচ্চ দৈর্ঘ্য (সেকেন্ডে)
    """
    if not temp_folder:
        temp_folder = TEMP_FOLDER
    
    # অডিওর ফাইলনাম থেকে বেস নাম পাই
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # অডিও চাঙ্কের জন্য একটি ফোল্ডার তৈরি করি
    chunks_folder = os.path.join(temp_folder, f"{base_name}_chunks")
    os.makedirs(chunks_folder, exist_ok=True)

    # অডিও দৈর্ঘ্য চেক করি
    try:
        duration_cmd = f'ffprobe -i "{audio_file}" -show_entries format=duration -v quiet -of csv="p=0"'
        duration = float(subprocess.check_output(duration_cmd, shell=True).decode().strip())
        print(f"📊 Audio duration: {duration:.2f}s ({duration/60:.2f} minutes)")
        
        # যদি অডিও দৈর্ঘ্য max_duration এর চেয়ে কম হয়, তবে চাঙ্কিং দরকার নেই
        if duration <= max_duration:
            print(f"✅ Audio is shorter than the maximum chunk size, no need to split")
            return [audio_file]
        
        # চাঙ্ক সংখ্যা গণনা করি
        num_chunks = math.ceil(duration / max_duration)
        print(f"🔪 Splitting audio into {num_chunks} chunks of max {max_duration/60:.2f} minutes each")
        
        chunk_files = []
        
        # প্রতিটি চাঙ্ক তৈরি করি
        for i in range(num_chunks):
            start_time = i * max_duration
            chunk_file = os.path.join(chunks_folder, f"{base_name}_chunk_{i+1}.mp3")
            
            # যদি এটি শেষ চাঙ্ক হয়, তবে শুধু শেষ অবধি নিই
            if i == num_chunks - 1:
                # শেষ চাঙ্কের জন্য ffmpeg কমান্ড
                chunk_cmd = f'ffmpeg -i "{audio_file}" -ss {start_time} -c:a libmp3lame -q:a 2 "{chunk_file}" -y'
            else:
                # মাঝখানের চাঙ্কের জন্য ffmpeg কমান্ড
                chunk_cmd = f'ffmpeg -i "{audio_file}" -ss {start_time} -t {max_duration} -c:a libmp3lame -q:a 2 "{chunk_file}" -y'
            
            # ffmpeg কমান্ড চালাই
            subprocess.run(chunk_cmd, shell=True)
            
            # যদি চাঙ্ক ফাইল সফলভাবে তৈরি হয়, তবে তালিকায় যোগ করি
            if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 0:
                chunk_files.append(chunk_file)
                print(f"✅ Created chunk {i+1}/{num_chunks}: {chunk_file}")
            else:
                print(f"❌ Failed to create chunk {i+1}/{num_chunks}")
        
        return chunk_files
        
    except Exception as e:
        print(f"❌ Error splitting audio into chunks: {e}")
        return [audio_file]  # সমস্যা হলে মূল ফাইল ফেরত দিই
    
def transcribe_audio(audio_file):
    """স্পিচ টু টেক্সট প্রসেস করা Whisper দিয়ে"""
    result = model.transcribe(audio_file, task='transcribe')
    if result and 'text' in result:
        return result['text']
    else:
        print(f"❌ Transcription failed for {audio_file}")
        return None


# Azure OpenAI API কল
def generate_output_from_azure(transcribe, video_title, output_file_path):
    """Azure OpenAI API দিয়ে স্পিচ টেক্সট প্রসেস করা এবং আউটপুট সেভ করা"""
    
    # প্রম্পট তৈরি
    prompt = f"""
    Here is my transcribe: {transcribe}
    Topic: "{video_title}"
    
    Write 1 Youtube relevent Video Title, Must engaging. 
    Write 2 paragraphs based on transcribe and title.
    Write 10 hashtags.
    Write 10 normal tags with comma separation.

    And After this, write this also:

    🎤 Speakers in this video: 
    Tony Robbins

    🔊 Our speeches are created by, remixed or licensed to Tony Robbins Motivation.
    For licensing information, message geniusteam01@gmail.com

    🎥 The video footage in this video:
    All video footage used is licensed through either CC-BY, from various stock footage websites, or filmed by us. All Creative Commons footage is listed at the video's end and licensed under CC-BY 3.0. Film and TV shows used in the video are interwoven with the video's narrative, related to the video's topic, and corresponding to FAIR USE.
    """
    
    # API Key এবং Endpoint থেকে API URL সেট করুন
    api_key = os.getenv("API_KEY")  # আপনার Azure OpenAI API Key 
    url = f'{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview'

    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key  # API Key
    }

    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI assistant that helps people find information."},
            {"role": "user", "content": prompt}  # এখানে prompt ব্যবহার করেছি
        ],
        "max_tokens": 1500,
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data['choices'][0]['message']['content'].strip()  # সঠিক টেক্সট যাচাই
            print(f"✅ Response received: {result[:200]}...")  # আংশিক আউটপুট
        else:
            print(f"❌ API Response Error: {response.status_code}, {response.text}")
            return

        # আউটপুট ফাইল সেভ করুন
        with open(output_file_path, "w", encoding="utf-8") as file:
            file.write(result)
            print(f"✅ Output saved to: {output_file_path}")

    except Exception as e:
        print(f"❌ Error generating output from Azure OpenAI: {e}")
        print("⚠️ Skipping Azure process and continuing with the next steps...")


def process_audio_and_generate_text(audio_file, video_title, is_short=False):
    """স্পিচ টু টেক্সট প্রসেস এবং Azure OpenAI এর মাধ্যমে আউটপুট তৈরি করা"""
    
    # Whisper এর মাধ্যমে অডিও থেকে ট্রান্সক্রিপ্ট করা
    transcribe = transcribe_audio(audio_file)

    if not transcribe:
        return
    
    # সেনিটাইজ করা ফাইল নাম থেকে অরিজিনাল ফাইল নাম খুঁজুন
    original_folder_name = get_original_basename(audio_file)
    sanitized_folder_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # যদি অরিজিনাল ফোল্ডার নাম না পাওয়া যায়, তাহলে সেনিটাইজ করা নাম ব্যবহার করুন
    if not original_folder_name:
        original_folder_name = sanitized_folder_name
    
    # অরিজিনাল ফাইল নাম অনুযায়ী ফোল্ডার তৈরি করুন
    if is_short:
        video_folder = os.path.join(OUTPUT_FOLDER, "shorts", original_folder_name)  # Shorts folder
    else:
        video_folder = os.path.join(OUTPUT_FOLDER, original_folder_name)  # Regular video folder

    os.makedirs(video_folder, exist_ok=True)

    # ভিডিও টাইটেল অনুযায়ী আউটপুট ফাইল নাম তৈরি করা (সেনিটাইজ করা নাম ব্যবহার করে)
    output_file_path = os.path.join(video_folder, f"{sanitized_folder_name}_output.txt")

    # Azure OpenAI API দিয়ে আউটপুট তৈরি করা
    generate_output_from_azure(transcribe, video_title, output_file_path)
    
    # Save video to the same folder (এটি create_video ফাংশনেই করা হয়েছে)
    print(f"✅ Video and text saved to: {video_folder}")


# ফাইল ব্যবহারের ট্র্যাকিং রাখার জন্য ডিকশনারি
file_usage_count = {}

def get_random_file(folder_path, extensions=(".mp4", ".mov", ".mp3", ".wav")):
    """ফোল্ডার থেকে সবচেয়ে কম ব্যবহৃত ফাইল নির্বাচন করে।"""
    global file_usage_count
    
    print(f"🔍 Checking folder: {folder_path}")
    if not os.path.isdir(folder_path):
        print(f"❌ Folder does not exist: {folder_path}")
        return None
        
    file_list = [f for f in glob(os.path.join(folder_path, "*")) if f.lower().endswith(extensions)]
    
    print(f"📋 Found {len(file_list)} files with extensions {extensions}")
    print(f"📄 Files: {[os.path.basename(f) for f in file_list]}")
    
    if not file_list:
        print(f"❌ No matching files found in folder")
        return None
    
    # সব ফাইলের ব্যবহার কাউন্ট চেক করুন
    # যদি ফাইল আগে ব্যবহার না হয়ে থাকে, তার কাউন্ট 0 ধরে নিন
    for file in file_list:
        if file not in file_usage_count:
            file_usage_count[file] = 0
    
    # সবচেয়ে কম ব্যবহৃত ফাইলগুলি খুঁজুন
    min_usage = min(file_usage_count[file] for file in file_list)
    least_used_files = [file for file in file_list if file_usage_count[file] == min_usage]
    
    # সবচেয়ে কম ব্যবহৃত ফাইলগুলি থেকে র‍্যান্ডমলি একটি নির্বাচন করুন
    selected_file = random.choice(least_used_files)
    
    # নির্বাচিত ফাইলের ব্যবহার কাউন্ট বাড়ান
    file_usage_count[selected_file] += 1
    
    print(f"✅ Selected file: {os.path.basename(selected_file)} (used {file_usage_count[selected_file]} times)")
    
    return selected_file

# আউটপুট ভিডিও ফাইলের নাম তৈরি করতে ফাইলের নামকে অডিও ফাইলের নাম অনুযায়ী সেট করুন
def get_output_filename(audio_file, is_short=False, prefix='', suffix=''):
    """
    অডিও ফাইলের নাম অনুযায়ী আউটপুট ভিডিও নাম তৈরি করুন, প্রিফিক্স ও সাফিক্স সহ।
    এখন এটি অরিজিনাল ফাইলনাম ব্যবহার করে ফোল্ডার তৈরি করে।
    """
    # সেনিটাইজ করা ফাইল পাথ থেকে অরিজিনাল ফাইলনাম খুঁজুন
    original_audio_filename = get_original_basename(audio_file)
    # যদি অরিজিনাল নাম না পাওয়া যায়, তাহলে বর্তমান ফাইলের নাম ব্যবহার করুন
    if not original_audio_filename:
        original_audio_filename = os.path.splitext(os.path.basename(audio_file))[0]
    
    sanitized_audio_filename = os.path.splitext(os.path.basename(audio_file))[0]
    
    if prefix:
        sanitized_audio_filename = prefix + sanitized_audio_filename
    if suffix:
        sanitized_audio_filename = sanitized_audio_filename + suffix

    # অস্থায়ী ফাইল পাথ হিসাবে TEMP_FOLDER ব্যবহার করুন
    if is_short:
        output_filename = os.path.join(TEMP_FOLDER, f"{sanitized_audio_filename}_short.mp4")
    else:
        output_filename = os.path.join(TEMP_FOLDER, f"{sanitized_audio_filename}.mp4")
    
    return output_filename


def convert_srt_to_ass(srt_file, ass_file, is_short=False, position='bottom'):
    """Convert SRT subtitles to ASS format with premium styling and random color patterns."""
    """
    position এর অপশন হতে পারে:
    - 'top'
    - 'bottom' (default)
    - 'left'
    - 'right'
    - 'center'
    """
    try:
        # ফাইলনাম এক্সট্রাক্ট করুন
        base_filename = os.path.basename(srt_file)
        
        print(f"\n🎨 Creating design for: {base_filename}")
        
        subs = pysubs2.load(srt_file, encoding="utf-8")
        
         # পজিশন অনুযায়ী alignment সেট করুন
        if position == 'top':
            subs.styles["Default"].alignment = 8  # Top
        elif position == 'bottom':
            subs.styles["Default"].alignment = 2  # Bottom
        elif position == 'left':
            subs.styles["Default"].alignment = 4  # Left
        elif position == 'right':
            subs.styles["Default"].alignment = 6  # Right
        else:  # center
            subs.styles["Default"].alignment = 5  # Center
        
        # ডিজাইন অ্যাপ্লাই করুন, ফাইলনাম পাস করুন যাতে একই ফাইলে সবসময় একই ডিজাইন হয়
        subs = apply_design(subs, is_short, filename=base_filename)
        
        # ASS ফাইল হিসেবে সংরক্ষণ করুন
        subs.save(ass_file)
        print(f"✅ Converted SRT to ASS with unique design: {ass_file}")
    except Exception as e:
        print(f"❌ Error converting subtitle to ASS: {e}")
        # ফলব্যাক ডিজাইন
        try:
            subs = pysubs2.load(srt_file, encoding="utf-8")
            subs.styles["Default"].fontname = "Arial"
            subs.styles["Default"].fontsize = 24 if is_short else 30
            subs.styles["Default"].primarycolor = pysubs2.Color(255, 255, 255, 0)
            subs.styles["Default"].outlinecolor = pysubs2.Color(0, 0, 0, 0)
            subs.styles["Default"].backcolor = pysubs2.Color(0, 0, 0, 128)
            subs.styles["Default"].borderstyle = 3
            subs.styles["Default"].outline = 2
            subs.styles["Default"].shadow = 0
            subs.styles["Default"].alignment = 2
            subs.save(ass_file)
            print(f"✅ Used fallback subtitle design: {ass_file}")
        except Exception as fallback_error:
            print(f"❌ Even fallback design failed: {fallback_error}")
            
def clear_temp_folder():
    """Clear temporary folder."""
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)
    os.makedirs(TEMP_FOLDER, exist_ok=True)

def shorten_filename(filename, length=10):
    """Shorten filenames to avoid issues with long paths."""
    base_name = os.path.splitext(os.path.basename(filename))[0]
    short_name = "_".join(base_name.split()[:length])
    return f"{short_name}_{''.join(random.choices(string.ascii_letters + string.digits, k=5))}"

def download_youtube_audio(url_file):
    """
    Download YouTube audio as MP3 and sanitize filenames.
    আপডেটেড: এরর হ্যান্ডলিং যোগ করা হয়েছে, একইসাথে একাধিক ইউটিউব লিংকে সমস্যা এড়ানো হয়েছে।
    """
    if not os.path.isfile(url_file):
        print(f"❌ URL ফাইল নেই: {url_file}")
        return []
        
    # ফাইল থেকে URL গুলো লোড করুন
    try:
        with open(url_file, "r", encoding="utf-8") as file:
            urls = [line.strip() for line in file.readlines() if line.strip()]
    except Exception as e:
        print(f"❌ URL ফাইল পড়তে সমস্যা: {url_file} - {e}")
        return []
        
    if not urls:
        print(f"⚠️ URL ফাইলে কোনো লিংক নেই: {url_file}")
        return []

    print(f"📋 {len(urls)}টি লিংক পাওয়া গেছে ফাইল থেকে: {url_file}")
    
    # সফল ডাউনলোড করা ফাইলগুলো সংরক্ষণের জন্য লিস্ট
    downloaded_files = []
    
    # প্রতিটি URL একে একে প্রসেস করুন (একসাথে সবগুলো করলে এরর হতে পারে)
    for idx, url in enumerate(urls, 1):
        print(f"\n🔄 প্রসেসিং URL {idx}/{len(urls)}: {url}")
        
        # এই URL এর জন্য অস্থায়ী ফোল্ডার তৈরি করুন
        temp_download_folder = os.path.join(TEMP_FOLDER, f"download_{int(time.time())}_{idx}")
        os.makedirs(temp_download_folder, exist_ok=True)
        
        # yt-dlp কনফিগারেশন 
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(temp_download_folder, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False
        }
        
        # এই URL ডাউনলোড করার চেষ্টা করুন
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', f"video_{idx}")
                print(f"🎬 ডাউনলোড করা হচ্ছে: {video_title}")
                ydl.download([url])
            
            # ডাউনলোড করা ফাইল খুঁজুন
            temp_files = glob(os.path.join(temp_download_folder, "*.mp3"))
            
            if not temp_files:
                print(f"⚠️ ডাউনলোড হয়েছে কিন্তু ফাইল পাওয়া যায়নি: {temp_download_folder}")
                continue
                
            # প্রথম ফাইল নিন (সাধারণত একটাই থাকে)
            downloaded_file = temp_files[0]
            
            # ফাইল অডিও ফোল্ডারে মুভ করুন এবং নাম সেনিটাইজ করুন
            file_name = os.path.basename(downloaded_file)
            sanitized_name, original_name = sanitize_filename(file_name)
            
            # অডিও ফোল্ডারে আছে কিনা চেক করুন
            target_path = os.path.join(AUDIO_FOLDER, sanitized_name)
            if os.path.exists(target_path):
                print(f"⚠️ ফাইল ইতিমধ্যে বিদ্যমান: {target_path}")
                # ইউনিক নাম তৈরি করুন
                base_name, ext = os.path.splitext(sanitized_name)
                sanitized_name = f"{base_name}_{int(time.time())}{ext}"
                target_path = os.path.join(AUDIO_FOLDER, sanitized_name)
                
            # ফাইল মুভ করুন
            try:
                shutil.move(downloaded_file, target_path)
                print(f"✅ ফাইল সফলভাবে সংরক্ষিত হয়েছে: {sanitized_name}")
                
                # ম্যাপিং সংরক্ষণ করুন
                map_filename(original_name, target_path)
                downloaded_files.append(target_path)
                
            except Exception as e:
                print(f"❌ ফাইল মুভ করতে সমস্যা: {e}")
                
            # অস্থায়ী ফোল্ডার পরিষ্কার করুন
            try:
                shutil.rmtree(temp_download_folder)
            except:
                pass
                
        except Exception as e:
            print(f"❌ URL ডাউনলোড করতে সমস্যা: {url} - {e}")
            print("⚠️ এই URL-টি এড়িয়ে পরবর্তী URL প্রসেস করা হচ্ছে...")
            
            # অস্থায়ী ফোল্ডার পরিষ্কার করুন
            try:
                shutil.rmtree(temp_download_folder)
            except:
                pass
    
    print(f"✅ মোট {len(downloaded_files)}টি ফাইল সফলভাবে ডাউনলোড করা হয়েছে {url_file} থেকে!")
    return downloaded_files


def load_processed_urls():
    """
    ইতিমধ্যে প্রসেস করা URLs গুলো লোড করুন
    """
    processed_urls = set()
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                processed_urls = set(line.strip() for line in f if line.strip())
        except Exception as e:
            print(f"❌ লগ ফাইল পড়তে সমস্যা: {e}")
    return processed_urls

def save_processed_url(url):
    """
    URL কে log ফাইলে সংরক্ষণ করুন
    """
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{url}\n")
        print(f"✅ URL লগ ফাইলে সংরক্ষিত হয়েছে: {url}")
    except Exception as e:
        print(f"❌ URL লগ ফাইলে সংরক্ষণ করতে সমস্যা: {e}")

def remove_url_from_file(url, file_path):
    """
    URL টিকে মূল URL ফাইল থেকে মুছে দিন
    """
    try:
        # ফাইল পড়ুন
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = f.readlines()
        
        # URL বাদ দিন (স্ট্রিংয়ের মাঝের স্পেস এবং লাইন ব্রেক ট্রিম করে)
        urls = [u for u in urls if u.strip() != url.strip()]
        
        # ফাইলে আবার লিখুন
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(urls)
        
        print(f"✅ URL মুছে দেওয়া হয়েছে: {url}")
    except Exception as e:
        print(f"❌ URL মুছতে সমস্যা: {url} - {e}")

def process_all_url_files():
    """
    URL ফাইলগুলো 1 by 1 প্রসেস করবে
    """
    # ইতিমধ্যে প্রসেসকৃত URLs লোড করুন
    processed_urls = load_processed_urls()

    # URL ফাইলগুলো
    url_files = [
        YOUTUBE_SHORTS_WITH_FACE_URL_FILE,
        YOUTUBE_LONG_WITH_FACE_URL_FILE,
        YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE,
        YOUTUBE_LONG_WITH_FACE_AI_URL_FILE,
        YOUTUBE_AI_VOICE_SHORTS_URL_FILE,
        YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE,
        YOUTUBE_URL_FILE,
        YOUTUBE_SHORTS_URL_FILE
    ]

    # প্রতিটি URL ফাইল প্রসেস করা
    for file_path in url_files:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            print(f"⚠️ ফাইল খালি বা নেই: {file_path}")
            continue

        # ফাইল থেকে URLs পড়ুন
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        print(f"\n🔍 {file_path} থেকে {len(urls)}টি URL প্রসেস করা হচ্ছে")

        # URLs গুলো 1 by 1 প্রসেস করুন
        for url in urls:
            # ইতিমধ্যে প্রসেস করা হয়েছে কিনা চেক করুন
            if url in processed_urls:
                print(f"⏩ URL ইতিমধ্যে প্রসেস করা হয়েছে: {url}")
                continue

            # URL কনফিগারেশন নির্ধারণ
            is_short = file_path in [
                YOUTUBE_SHORTS_WITH_FACE_URL_FILE, 
                YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE, 
                YOUTUBE_AI_VOICE_SHORTS_URL_FILE, 
                YOUTUBE_SHORTS_URL_FILE
            ]

            use_ai_voice = file_path in [
                YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE, 
                YOUTUBE_LONG_WITH_FACE_AI_URL_FILE, 
                YOUTUBE_AI_VOICE_SHORTS_URL_FILE, 
                YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE
            ]

            use_face_footage = file_path in [
                YOUTUBE_SHORTS_WITH_FACE_URL_FILE, 
                YOUTUBE_LONG_WITH_FACE_URL_FILE, 
                YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE, 
                YOUTUBE_LONG_WITH_FACE_AI_URL_FILE
            ]

            print(f"\n===== URL প্রসেসিং: {url} =====")
            print(f"⚙️ কনফিগারেশন: শর্টস={is_short}, AI ভয়েস={use_ai_voice}, ফেস ফুটেজ={use_face_footage}")

            # URL ফাইল তৈরি করে প্রসেস করুন
            temp_url_file = os.path.join(BASE_PATH, f"temp_url_{int(time.time())}.txt")
            with open(temp_url_file, 'w', encoding='utf-8') as f:
                f.write(url)

            try:
                # ডাউনলোড এবং প্রসেস
                audio_files = download_youtube_audio(temp_url_file)
                
                if not audio_files:
                    print(f"❌ {url} থেকে কোনো অডিও ফাইল ডাউনলোড হয়নি")
                    
                    # URL কে log ফাইলে যোগ করুন
                    save_processed_url(url)
                    
                    # URL টিকে মূল ফাইল থেকে মুছে দিন
                    remove_url_from_file(url, file_path)
                    
                    # টেম্পরারি URL ফাইল মুছে দিন
                    os.remove(temp_url_file)
                    
                    continue

                print(f"✅ {len(audio_files)}টি অডিও ফাইল ডাউনলোড সম্পন্ন হয়েছে")

                # প্রতিটি অডিও ফাইল প্রসেস করুন
                for audio_file in audio_files:
                    video_title = os.path.splitext(os.path.basename(audio_file))[0]
                    print(f"\n🎵 অডিও প্রসেসিং: {video_title}")

                    # ভিডিও তৈরি
                    success = process_audio_in_parallel(
                        audio_file, 
                        is_short=is_short, 
                        use_ai_voice=use_ai_voice, 
                        use_face_footage=use_face_footage
                    )

                    if success:
                        print(f"✅ সফলভাবে ভিডিও তৈরি হয়েছে: {video_title}")
                        
                        # URL কে log ফাইলে যোগ করুন
                        save_processed_url(url)
                        
                        # URL টিকে মূল ফাইল থেকে মুছে দিন
                        remove_url_from_file(url, file_path)
                    else:
                        print(f"❌ ভিডিও তৈরি করতে ব্যর্থ: {video_title}")

                # টেম্পরারি URL ফাইল মুছে দিন
                os.remove(temp_url_file)

            except Exception as e:
                print(f"❌ URL প্রসেসিং এরর: {url} - {e}")
                
                # URL কে log ফাইলে যোগ করুন
                save_processed_url(url)
                
                # URL টিকে মূল ফাইল থেকে মুছে দিন
                remove_url_from_file(url, file_path)
                
                # টেম্পরারি URL ফাইল মুছে দিন
                os.remove(temp_url_file)

    print("\n🎉 সব URL ফাইল প্রসেসিং সম্পন্ন!")
# remove_background_music ফাংশনটি পরিবর্তন করুন
def remove_background_music(input_audio, output_audio, temp_folder):
    """
    Spleeter দিয়ে ব্যাকগ্রাউন্ড মিউজিক থেকে ভয়েস আলাদা করে। 
    যদি Spleeter ইনস্টল না থাকে বা ব্যর্থ হয়, তাহলে FFmpeg ফিল্টার ব্যবহার করে।
    """
    try:
        print(f"🔊 Processing audio file to separate voice from background: {input_audio}")
        
        # অডিওর দৈর্ঘ্য চেক করুন
        duration_cmd = f'ffprobe -i "{input_audio}" -show_entries format=duration -v quiet -of csv="p=0"'
        try:
            duration = float(subprocess.check_output(duration_cmd, shell=True).decode().strip())
            print(f"Audio duration: {duration} seconds ({duration/60:.2f} minutes)")
        except:
            print("Could not determine audio duration")

        # Spleeter টেম্প ডিরেক্টরি
        spleeter_output = os.path.join(temp_folder, "spleeter_output")
        os.makedirs(spleeter_output, exist_ok=True)
        
        # প্রথমে Spleeter দিয়ে চেষ্টা করুন
        try:
            # Spleeter কমান্ড চালান
            spleeter_cmd = f'spleeter separate -o "{spleeter_output}" -p spleeter:2stems "{input_audio}"'
            
            # Spleeter এর পরে অতিরিক্ত পোস্ট-প্রসেসিং যোগ করুন:
            enhance_cmd = (
                f'ffmpeg -i "{vocals_path}" -af "equalizer=f=1000:width_type=o:width=1:g=2,' 
                f'equalizer=f=3000:width_type=o:width=1:g=3,' 
                f'equalizer=f=6000:width_type=o:width=1:g=1,' 
                f'loudnorm=I=-14:TP=-1.5:LRA=11,' 
                f'volume=1.2" '
                f'-c:a pcm_s24le -ar 48000 "{output_audio}" -y'
            )
            
            print("Running Spleeter for voice separation...")
            subprocess.run(spleeter_cmd, shell=True, timeout=300)  # 5 মিনিট টাইমআউট
            
            # Spleeter আউটপুট পাথ - অডিও নাম অনুযায়ী ফোল্ডার তৈরি করে
            audio_name = os.path.splitext(os.path.basename(input_audio))[0]
            vocals_path = os.path.join(spleeter_output, audio_name, "vocals.wav")
            
            if os.path.exists(vocals_path):
                # ভয়েস কোয়ালিটি উন্নত করুন
                enhance_cmd = (
                    f'ffmpeg -i "{vocals_path}" -af "volume=1.5, ' 
                    f'compand=attacks=0.01:decays=0.1:points=-80/-80|-45/-45|-27/-25|-15/-10|-5/-2|0/0|20/8" '
                    f'-c:a pcm_s16le "{output_audio}" -y'
                )
                subprocess.run(enhance_cmd, shell=True)
                print(f"✅ Successfully separated and enhanced vocals using Spleeter")
                return
            else:
                print(f"⚠️ Spleeter output file not found: {vocals_path}")
                raise FileNotFoundError(f"Spleeter output file not found: {vocals_path}")
                
        except Exception as spleeter_error:
            print(f"⚠️ Spleeter failed or not installed: {spleeter_error}")
            print("Falling back to FFmpeg filters for voice enhancement...")
        
        # যদি Spleeter ব্যর্থ হয়, তাহলে FFmpeg ফিল্টার ব্যবহার করুন
        # উন্নত FFmpeg অডিও ফিল্টার
        audio_filter = (
            "highpass=f=60, " +           # নিচু আওয়াজ বাদ দিন
            "lowpass=f=12000, " +          # উচ্চ আওয়াজ বাদ দিন
            "volume=1.5, " +              # ভলিউম বাড়ান
            "compand=attacks=0.02:decays=0.2:" +  # ডাইনামিক কম্প্রেশন
            "points=-70/-70|-40/-40|-25/-24|-15/-12|-5/-5|0/0|15/7"
        )
        
        ffmpeg_cmd = (
            f'ffmpeg -i "{input_audio}" -af "{audio_filter}" '
            f'-c:a pcm_s24le -ar 48000 "{output_audio}" -y'  # ইম্প্রুভড বিট ডেপথ ও স্যাম্পলিং রেট
        )
        print(f"Running FFmpeg audio enhancement command...")
        subprocess.run(ffmpeg_cmd, shell=True)
        
        # আউটপুট ফাইল যাচাই করুন
        if os.path.exists(output_audio):
            try:
                out_duration = float(subprocess.check_output(
                    f'ffprobe -i "{output_audio}" -show_entries format=duration -v quiet -of csv="p=0"',
                    shell=True
                ).decode().strip())
                print(f"✅ Enhanced audio duration: {out_duration} seconds ({out_duration/60:.2f} minutes)")
            except:
                print("Could not determine output audio duration")
            
            print(f"✅ Speech enhanced using FFmpeg filters: {output_audio}")
        else:
            print(f"❌ Output file not created: {output_audio}")
            # প্রসেসিং ব্যর্থ হলে, সাধারণ কপি করুন
            shutil.copy2(input_audio, output_audio)
            print(f"✅ Copied original file as fallback: {output_audio}")
            
    except Exception as e:
        print(f"❌ Error processing audio: {e}")
        # সবকিছু ব্যর্থ হলে সাধারণ কপি করুন
        try:
            shutil.copy2(input_audio, output_audio)
            print(f"✅ File copied as fallback: {output_audio}")
        except Exception as copy_error:
            print(f"❌ Even fallback copy failed: {copy_error}")

def process_long_audio_with_chunked_transcription(audio_file, audio_temp_folder):
    """
    দীর্ঘ অডিও ফাইলকে চাংকে ভাগ করে, প্রতিটি চাংকের
    1. ব্যাকগ্রাউন্ড মিউজিক রিমুভ করে
    2. প্রতিটি চাংক আলাদাভাবে ট্রান্সক্রাইব করে
    3. সব ট্রান্সক্রিপ্ট একত্রিত করে
    4. একত্রিত ট্রান্সক্রিপ্ট থেকে AI ভয়েস তৈরি করে
    
    এটি শুধুমাত্র AI ভয়েস ফিচারের জন্য ব্যবহার করুন
    
    Returns:
        str: AI ভয়েস অডিও ফাইলের পাথ, ব্যর্থ হলে None
    """
    audio_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    # অডিও দৈর্ঘ্য চেক করুন
    try:
        duration_cmd = f'ffprobe -i "{audio_file}" -show_entries format=duration -v quiet -of csv="p=0"'
        audio_duration = float(subprocess.check_output(duration_cmd, shell=True).decode().strip())
        print(f"📊 Audio duration: {audio_duration:.2f}s ({audio_duration/60:.2f} minutes)")
        
        # 10 মিনিটের কম হলে চাংকিং প্রয়োজন নেই
        if audio_duration <= 600:
            print(f"✅ Audio is shorter than 10 minutes, processing without chunking")
            filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
            remove_background_music(audio_file, filtered_audio, audio_temp_folder)
            
            # সম্পূর্ণ ফাইল ট্রান্সক্রাইব করুন
            transcript = transcribe_audio(filtered_audio)
            
            if transcript:
                print(f"✅ Transcription successful: {len(transcript.split())} words")
                ai_voice_file = transcribe_and_generate_ai_voice(transcript, audio_name, audio_temp_folder)
                
                if ai_voice_file and os.path.exists(ai_voice_file):
                    print(f"✅ Using AI voice: {ai_voice_file}")
                    return ai_voice_file
            
            return None
        
        # এখানে অডিও চাংকিং করা হবে
        print("🔄 Audio is longer than 10 minutes, using chunked transcription...")
        
        # চাংক ফোল্ডার তৈরি করুন
        chunks_folder = os.path.join(audio_temp_folder, "chunks")
        os.makedirs(chunks_folder, exist_ok=True)
        
        # উন্নত - চাংক সাইজ কমিয়ে আনুন ট্রান্সক্রিপশন এক্যুরেসির জন্য
        chunk_size = 180  # 3 মিনিট (আগের থেকে আরও কম)
        
        # চাংক সংখ্যা গণনা
        num_chunks = math.ceil(audio_duration / chunk_size)
        print(f"🔪 Splitting audio into {num_chunks} chunks of {chunk_size/60:.1f} minutes each")
        
        # প্রতিটি চাংক তৈরি, প্রসেস, এবং ট্রান্সক্রাইব
        all_transcripts = []
        
        for i in range(num_chunks):
            start_time = i * chunk_size
            
            # শেষ চাংকের জন্য যদি বাকি সময় কম থাকে
            if i == num_chunks - 1:
                duration = audio_duration - start_time
            else:
                duration = chunk_size
            
            print(f"\n--- Processing Chunk {i+1}/{num_chunks} (Duration: {duration:.1f}s) ---")
            
            # চাংক ফাইল পাথ
            chunk_file = os.path.join(chunks_folder, f"chunk_{i+1}.mp3")
            
            # ffmpeg দিয়ে চাংক তৈরি - সর্বোচ্চ 3 বার চেষ্টা করবে
            max_attempts = 3
            chunk_success = False
            
            for attempt in range(max_attempts):
                try:
                    chunk_cmd = f'ffmpeg -i "{audio_file}" -ss {start_time} -t {duration} -c:a libmp3lame -q:a 2 "{chunk_file}" -y'
                    subprocess.run(chunk_cmd, shell=True, timeout=300)
                    
                    if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 1000:
                        chunk_success = True
                        print(f"✅ Created chunk {i+1}/{num_chunks} (Attempt {attempt+1})")
                        break
                except Exception as e:
                    print(f"⚠️ Error creating chunk {i+1}, attempt {attempt+1}: {e}")
            
            if not chunk_success:
                print(f"❌ Failed to create chunk {i+1} after {max_attempts} attempts, skipping")
                continue
            
            # প্রতিটি চাংকের ব্যাকগ্রাউন্ড মিউজিক রিমুভ করুন
            filtered_chunk = os.path.join(chunks_folder, f"chunk_{i+1}_filtered.wav")
            print(f"🔊 Removing background from chunk {i+1}/{num_chunks}")
            
            # ব্যাকগ্রাউন্ড রিমুভাল - সর্বোচ্চ 2 বার চেষ্টা
            filter_success = False
            for attempt in range(2):
                try:
                    remove_background_music(chunk_file, filtered_chunk, chunks_folder)
                    
                    if os.path.exists(filtered_chunk) and os.path.getsize(filtered_chunk) > 1000:
                        filter_success = True
                        print(f"✅ Filtered chunk {i+1}/{num_chunks} (Attempt {attempt+1})")
                        break
                except Exception as e:
                    print(f"⚠️ Error filtering chunk {i+1}, attempt {attempt+1}: {e}")
            
            # ফিল্টার ব্যর্থ হলে অরিজিনাল ব্যবহার করুন
            if not filter_success:
                print(f"⚠️ Using original chunk without filtering for chunk {i+1}")
                # অরিজিনাল চাংক WAV ফরম্যাটে কনভার্ট করুন
                wav_chunk = os.path.join(chunks_folder, f"chunk_{i+1}_original.wav")
                try:
                    convert_cmd = f'ffmpeg -i "{chunk_file}" -c:a pcm_s16le "{wav_chunk}" -y'
                    subprocess.run(convert_cmd, shell=True)
                    if os.path.exists(wav_chunk) and os.path.getsize(wav_chunk) > 0:
                        filtered_chunk = wav_chunk
                    else:
                        filtered_chunk = chunk_file
                except:
                    filtered_chunk = chunk_file
            
            # ৩. এখানে প্রতিটি চাংক আলাদা আলাদা ট্রান্সক্রাইব করুন
            print(f"🎙️ Transcribing chunk {i+1}/{num_chunks}...")
            chunk_transcript = transcribe_audio(filtered_chunk)
            
            if chunk_transcript:
                print(f"✅ Chunk {i+1} transcription successful: {len(chunk_transcript.split())} words")
                # শুরুতে চাংক নম্বর যোগ করুন - পরে ডিবাগিং এর জন্য
                chunk_transcript = f"[Chunk {i+1}] {chunk_transcript}"
                all_transcripts.append(chunk_transcript)
            else:
                print(f"❌ Chunk {i+1} transcription failed")
        
        # যদি কোনো চাংক ট্রান্সক্রাইব না হয়
        if not all_transcripts:
            print("❌ No chunks were successfully transcribed")
            return None
        
        # ৪. সব ট্রান্সক্রিপ্ট একত্রিত করুন
        full_transcript = " ".join(all_transcripts)
        print(f"\n✅ Combined all transcripts: {len(full_transcript.split())} words total")
        
        # ট্রান্সক্রিপ্ট ফাইলে সংরক্ষণ করুন (ঐচ্ছিক - ডিবাগিং এর জন্য)
        transcript_file = os.path.join(audio_temp_folder, f"{audio_name}_transcript.txt")
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(full_transcript)
        
        # ৫. AI ভয়েস জেনারেট করুন
        print(f"🎙️ Generating AI voice from combined transcript...")
        ai_voice_file = transcribe_and_generate_ai_voice(full_transcript, audio_name, audio_temp_folder)
        
        if ai_voice_file and os.path.exists(ai_voice_file):
            print(f"✅ AI voice generation successful: {ai_voice_file}")
            return ai_voice_file
        else:
            print(f"❌ AI voice generation failed")
            return None
        
    except Exception as e:
        print(f"❌ Error in chunked transcription process: {e}")
        return None

def split_into_chunks(result, words_per_line=5):
    """
    Whisper result ডেটা থেকে (word_timestamps=True) প্রতিটি ওয়ার্ড নিয়ে 
    ছোট ছোট চাঙ্ক (সাবটাইটেল লাইন) তৈরি করে রিটার্ন করবে।
    """
    all_chunks = []
    current_words = []
    chunk_start_time = None
    chunk_end_time = None

    for seg in result["segments"]:
        for w in seg["words"]:
            if chunk_start_time is None:
                chunk_start_time = w["start"]
            chunk_end_time = w["end"]
            current_words.append(w["word"])

            if (len(current_words) >= words_per_line) or any(punct in w["word"] for punct in [".", "!", "?", ","]):
                text_line = " ".join(current_words).strip()
                all_chunks.append({
                    "start": chunk_start_time,
                    "end": chunk_end_time,
                    "text": text_line
                })
                current_words = []
                chunk_start_time = None
                chunk_end_time = None
    
    if current_words:
        text_line = " ".join(current_words).strip()
        all_chunks.append({
            "start": chunk_start_time,
            "end": chunk_end_time,
            "text": text_line
        })

    return all_chunks

def color_line_dynamically(line, color1="&HFFFF00&", color2="&HFFFFFF&", ratio=0.7):
    """
    line: মূল টেক্সট (একটি সাবটাইটেল লাইন)
    color1: প্রথম অংশের রঙ (ASS BGR format, উদাহরণ: &H00FF00& = সবুজ)
    color2: পরের অংশের রঙ (ASS BGR format, উদাহরণ: &HFFFF00& = নীলাভ হলুদ নয়)
    ratio: কত শতাংশ শব্দ color1 এ থাকবে (ডিফল্ট 0.7 = 70%)
    """
    words = line.split()
    total_words = len(words)
    if total_words == 0:
        return line

    split_index = int(total_words * ratio)
    if split_index <= 0:
        return f"{{\\c{color2}}}{line}{{\\r}}"
    if split_index >= total_words:
        return f"{{\\c{color1}}}{line}{{\\r}}"

    part1 = words[:split_index]
    part2 = words[split_index:]
    text1 = " ".join(part1)
    text2 = " ".join(part2)
    return f"{{\\c{color1}}}{text1} {{\\c{color2}}}{text2}{{\\r}}"

def generate_subtitles(audio_file, subtitle_file, subtitle_format='srt'):
    """Generate smaller-chunk subtitles from audio file using word timestamps, with dynamic coloring and fade animation."""
    global model
    result = model.transcribe(audio_file, word_timestamps=True, task='transcribe')
    if not result or "segments" not in result or not result["segments"]:
        print(f"❌ Transcription failed or empty segments for: {audio_file}")
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write("")
        return

    chunks = split_into_chunks(result, words_per_line=5)
    def format_timestamp(seconds):
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millisecs:03}"

    fade_tag = r"{\fad(300,300)}"
    with open(subtitle_file, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, start=1):
            start_ts = format_timestamp(chunk["start"])
            end_ts = format_timestamp(chunk["end"])
            text_line = chunk["text"]
            colored_text = color_line_dynamically(line=text_line, color1="&H00FF00&", color2="&HFFFFFF&", ratio=0.7)
            animated_text = fade_tag + colored_text
            if subtitle_format == 'srt':
                f.write(f"{i}\n{start_ts} --> {end_ts}\n{animated_text}\n\n")
            else:
                f.write(f"{animated_text}\n")
    print(f"✅ Subtitles generated (chunked): {subtitle_file}")


def clear_audio_and_temp_folders(audio_file, temp_folder):
    """Delete specific audio file and its related temp files."""
    # Delete the specific audio file
    if os.path.isfile(audio_file):
        os.remove(audio_file)
        print(f"✅ Deleted audio file: {audio_file}")

    # Identify temp folder specific to the audio file
    temp_audio_folder = os.path.join(temp_folder, os.path.splitext(os.path.basename(audio_file))[0])

    # Delete the folder and its contents
    if os.path.isdir(temp_audio_folder):
        shutil.rmtree(temp_audio_folder)
        print(f"✅ Deleted temporary folder: {temp_audio_folder}")

def create_video(stock_video, audio_file, output_video, is_short=False, use_karaoke=True, temp_folder=None, use_ai_voice=False, use_face_footage=False):
    """
    ভিডিও তৈরি করে:
      1. স্টক ভিডিও লুপ করে (স্কেল/প্যাড যদি শর্টস হয়)
      2. ব্যাকগ্রাউন্ড মিউজিক মিক্স করা
      3. সাবটাইটেল তৈরি (karaoke বা সাধারণ, use_karaoke ফ্ল্যাগ অনুযায়ী)
      4. ffmpeg দিয়ে সব মার্জ করা
      
    যদি use_ai_voice=True হয়, তাহলে Whisper দিয়ে ট্রান্সক্রিপ্ট করে AI ভয়েস জেনারেট করবে।
    যদি use_face_footage=True হয়, তাহলে প্রথমে ফেস ফুটেজ যোগ করবে।
    """
    if not temp_folder:
        temp_folder = TEMP_FOLDER
    
    # সেনিটাইজ করা অডিও ফাইল থেকে নাম নিন
    sanitized_folder_name = os.path.splitext(os.path.basename(audio_file))[0]
    # অরিজিনাল ফাইল নাম খুঁজুন
    original_folder_name = get_original_basename(audio_file)
    
    # যদি অরিজিনাল ফোল্ডার নাম না পাওয়া যায়, তাহলে সেনিটাইজ করা নাম ব্যবহার করুন
    if not original_folder_name:
        original_folder_name = sanitized_folder_name
    
    # ফোল্ডার তৈরি করুন অরিজিনাল নাম অনুযায়ী
    if is_short:
        video_folder = os.path.join(OUTPUT_FOLDER, "shorts", original_folder_name)  # Shorts folder
    else:
        video_folder = os.path.join(OUTPUT_FOLDER, original_folder_name)  # Regular video folder
    
    # ভিডিওর জন্য ইউনিক টেম্প ফোল্ডার
    video_specific_temp = os.path.join(temp_folder, f"{sanitized_folder_name}_{int(time.time())}")
    os.makedirs(video_specific_temp, exist_ok=True)
    
    # Make sure folder exists
    os.makedirs(video_folder, exist_ok=True)

    # Create video
    try:
        if is_short:
            random_stock = get_random_file(SHORTS_STOCK_VIDEOS_FOLDER, (".mp4", ".mov"))
            used_stock_video = random_stock if random_stock else stock_video
        else:
            random_stock = get_random_file(STOCK_VIDEOS_FOLDER, (".mp4", ".mov"))
            used_stock_video = random_stock if random_stock else stock_video

        print(f"🎬 Creating video (is_short={is_short}, karaoke={use_karaoke}, ai_voice={use_ai_voice}, face_footage={use_face_footage}): {output_video} ...")
        
        # যদি AI ভয়েস ব্যবহার করতে হয়
        if use_ai_voice:
            # Whisper দিয়ে ট্রান্সক্রিপ্ট করুন
            print("🎙️ Transcribing audio for AI voice generation...")
            transcript = transcribe_audio(audio_file)
            
            if transcript:
                # AI ভয়েস জেনারেট করুন
                ai_voice_file = transcribe_and_generate_ai_voice(transcript, sanitized_folder_name, video_specific_temp)
                
                if ai_voice_file and os.path.exists(ai_voice_file):
                    print(f"✅ Using AI voice: {ai_voice_file}")
                    main_audio = ai_voice_file
                else:
                    print("❌ AI voice generation failed, using original audio")
                    main_audio = audio_file
            else:
                print("❌ Transcription failed, using original audio")
                main_audio = audio_file
        else:
            main_audio = audio_file
        
        # অডিও ডিউরেশন চেক করুন
        audio_duration = float(
            subprocess.check_output(
                f'ffprobe -i "{main_audio}" -show_entries format=duration -v quiet -of csv="p=0"',
                shell=True
            ).decode().strip()
        )
        short_duration = min(audio_duration, 60) if is_short else audio_duration
        print(f"📊 Main audio duration: {short_duration:.2f}s")
        
        # ফেস ফুটেজ প্রসেসিং
        if use_face_footage:
            print("🎭 Processing face footage with guaranteed timing method...")
            # ফেস ফুটেজ নিন (সর্বোচ্চ 5 সেকেন্ডের)
            face_footage = face_handler.get_random_face_footage(is_short=is_short, max_duration=5.0)
            
            if not face_footage or not os.path.exists(face_footage):
                print("⚠️ No face footage available or file does not exist, using only stock footage")
                use_face_footage = False
            else:
                try:
                    # একটি সম্পূর্ণ নতুন পদ্ধতি ব্যবহার করা:
                    # 1. প্রথমে এমন একটি ভিডিও তৈরি করবো যেটি স্টক ভিডিওর লুপিং দিয়ে পুরো অডিও দৈর্ঘ্য কভার করে
                    # 2. তারপর ভিডিওর শুরুতে ফেস ফুটেজ বসিয়ে দেবো ভিডিও এডিটিং পদ্ধতিতে
                    # এতে টাইমিং সমস্যা এড়ানো যাবে
                    
                    # স্টেপ 1: সম্পূর্ণ অডিও দৈর্ঘ্যের জন্য স্টক ভিডিও তৈরি করুন
                    full_stock_video = os.path.join(video_specific_temp, "full_stock.mp4")
                    
                    if is_short:
                        # শর্টস ভিডিওর ক্ষেত্রে স্কেল করুন
                        scale_filter = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
                        stock_cmd = (
                            f'ffmpeg -stream_loop -1 -i "{used_stock_video}" -t {short_duration} '
                            f'-vf "{scale_filter}" -c:v libx264 -an -preset ultrafast -crf 23 '
                            f'"{full_stock_video}" -y'
                        )
                    else:
                        # রেগুলার ভিডিওর ক্ষেত্রে
                        stock_cmd = (
                            f'ffmpeg -stream_loop -1 -i "{used_stock_video}" -t {short_duration} '
                            f'-c:v libx264 -an -preset ultrafast -crf 23 "{full_stock_video}" -y'
                        )
                    
                    subprocess.run(stock_cmd, shell=True)
                    print(f"✅ Created full-length stock video base")
                    
                    # স্টেপ 2: ফেস ফুটেজ প্রসেস করুন (স্কেল, আকার ইত্যাদি)
                    face_processed = os.path.join(video_specific_temp, "face_processed.mp4")
                    
                    # ফেস ফুটেজের দৈর্ঘ্য চেক করুন
                    face_duration = float(
                        subprocess.check_output(
                            f'ffprobe -i "{face_footage}" -show_entries format=duration -v quiet -of csv="p=0"',
                            shell=True
                        ).decode().strip()
                    )
                    print(f"✅ Face footage duration: {face_duration:.2f}s")
                    
                    # ফেস ফুটেজের দৈর্ঘ্য সীমিত করুন (5 সেকেন্ডের বেশি নয়)
                    face_duration = min(face_duration, 5.0)
                    
                    if is_short:
                        face_cmd = (
                            f'ffmpeg -i "{face_footage}" -t {face_duration} '
                            f'-vf "{scale_filter}" -c:v libx264 -an -preset ultrafast -crf 23 '
                            f'"{face_processed}" -y'
                        )
                    else:
                        face_cmd = (
                            f'ffmpeg -i "{face_footage}" -t {face_duration} '
                            f'-c:v libx264 -an -preset ultrafast -crf 23 "{face_processed}" -y'
                        )
                    
                    subprocess.run(face_cmd, shell=True)
                    print(f"✅ Processed face footage (limited to {face_duration:.2f}s)")
                    
                    # স্টেপ 3: একটা 1-প্যাস কমান্ডে ভিডিও এডিটিংয়ের মাধ্যমে যোগ করুন
                    # overlay + enable=, seekable=1 কমান্ড ব্যবহার করে একটি ফুল ভিডিও তৈরি করবো
                    # এটা একই FFmpeg প্রক্রিয়ায় করবে, যাতে সিঙ্কিং সমস্যা না হয়
                    
                    final_no_audio = os.path.join(video_specific_temp, "final_no_audio.mp4")
                    
                    # এখানে overlay ফিল্টার ব্যবহার করে, ভিডিওর শুরুতে ফেস ফুটেজ প্লেস করা হচ্ছে
                    # এবং 5 সেকেন্ড বা face_duration পর্যন্ত দেখানো হচ্ছে শুধু
                    concat_cmd = (
                        f'ffmpeg -i "{full_stock_video}" -i "{face_processed}" -filter_complex '
                        f'"[1:v]setpts=PTS-STARTPTS[face];'
                        f'[0:v][face]overlay=0:0:enable=\'between(t,0,{face_duration})\''
                        f'[outv]" -map "[outv]" -an -c:v libx264 -preset fast -crf 22 '
                        f'"{final_no_audio}" -y'
                    )
                    
                    subprocess.run(concat_cmd, shell=True)
                    
                    # যাচাই করুন যে এডিটিং সফল হয়েছে
                    if os.path.exists(final_no_audio) and os.path.getsize(final_no_audio) > 1000:  # অন্তত 1KB
                        # ভিডিওর দৈর্ঘ্য চেক করুন
                        try:
                            video_duration = float(
                                subprocess.check_output(
                                    f'ffprobe -i "{final_no_audio}" -show_entries format=duration -v quiet -of csv="p=0"',
                                    shell=True
                                ).decode().strip()
                            )
                            print(f"✅ Final video duration: {video_duration:.2f}s, Audio duration: {short_duration:.2f}s")
                            
                            # যদি ভিডিও দৈর্ঘ্য অডিও দৈর্ঘ্যের সাথে মেলে না, তাহলে ট্রিম করুন
                            if abs(video_duration - short_duration) > 0.5:  # যদি 0.5 সেকেন্ডের বেশি পার্থক্য হয়
                                print(f"⚠️ Video duration mismatch, trimming to match audio")
                                trimmed_video = os.path.join(video_specific_temp, "trimmed_video.mp4")
                                trim_cmd = (
                                    f'ffmpeg -i "{final_no_audio}" -t {short_duration} '
                                    f'-c:v copy "{trimmed_video}" -y'
                                )
                                subprocess.run(trim_cmd, shell=True)
                                final_no_audio = trimmed_video
                        except Exception as e:
                            print(f"⚠️ Could not check video duration: {e}")
                        
                        used_video = final_no_audio
                        print(f"✅ Successfully created face+stock combined video")
                    else:
                        print(f"⚠️ Video editing failed, falling back to stock footage only")
                        use_face_footage = False
                
                except Exception as e:
                    print(f"❌ Error processing face footage: {e}")
                    use_face_footage = False
        
        # যদি ফেস ফুটেজ ব্যবহার না করা হয় বা ত্রুটি হয়, তাহলে স্ট্যান্ডার্ড ভিডিও প্রসেসিং
        if not use_face_footage:
            print("🎬 Using only stock footage...")
            # ভিডিও লুপ করে ও অন্যান্য প্রসেসিং একসাথে করুন
            stock_only_video = os.path.join(video_specific_temp, "stock_only.mp4")
            
            if is_short:
                scale_filter = (
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
                )
                stock_cmd = (
                    f'ffmpeg -stream_loop -1 -i "{used_stock_video}" -t {short_duration} '
                    f'-vf "{scale_filter}" -c:v libx264 -an -preset ultrafast -crf 22 "{stock_only_video}" -y'
                )
            else:
                stock_cmd = (
                    f'ffmpeg -stream_loop -1 -i "{used_stock_video}" -t {short_duration} '
                    f'-c:v libx264 -an -preset ultrafast -crf 22 "{stock_only_video}" -y'
                )
            
            subprocess.run(stock_cmd, shell=True)
            used_video = stock_only_video
        
        # ব্যাকগ্রাউন্ড মিউজিক প্রসেসিং - নতুন পদ্ধতি
        bgm_file = get_random_file(BACKGROUND_MUSIC_FOLDER, (".mp3", ".wav", ".m4a", ".ogg"))
        if bgm_file:
            print(f"🎵 Selected background music: {os.path.basename(bgm_file)}")
            
            # ব্যাকগ্রাউন্ড মিউজিক অডিও ডিউরেশন চেক করুন
            try:
                bgm_duration = float(
                    subprocess.check_output(
                        f'ffprobe -i "{bgm_file}" -show_entries format=duration -v quiet -of csv="p=0"',
                        shell=True
                    ).decode().strip()
                )
                print(f"🎵 Audio duration: {short_duration}s, BGM duration: {bgm_duration}s")
            except:
                bgm_duration = 0
                print("⚠️ Could not determine BGM duration")
            
            # ব্যাকগ্রাউন্ড মিউজিক লুপিং - অডিও দৈর্ঘ্য ঠিকমত সেট করা
            looped_bgm = os.path.join(video_specific_temp, "looped_bgm.mp3")
            loop_cmd = f'ffmpeg -stream_loop -1 -i "{bgm_file}" -t {short_duration} -c:a copy "{looped_bgm}" -y'
            subprocess.run(loop_cmd, shell=True)
            
            # এবার উচ্চ ভলিউমে ব্যাকগ্রাউন্ড মিউজিক যোগ করুন
            mixed_audio = os.path.join(video_specific_temp, "bgm_mixed_audio.m4a")
            print(f"🎚️ Mixing audio with higher BGM volume (0.5 or 50%)")
            
            mix_cmd = (
                f'ffmpeg -i "{main_audio}" -i "{looped_bgm}" -filter_complex '
                f'"[0:a]volume=1.5[speech];'
                f'[1:a]volume=0.3[music];'  # ব্যাকগ্রাউন্ড ভলিউম আরও কমাতে
                f'[speech][music]amix=inputs=2:duration=first:weights=7 1:dropout_transition=5" '  # ভয়েসের ওজন বাড়াতে
                f'-c:a aac -b:a 320k "{mixed_audio}" -y'  # বিটরেট বাড়ালাম
            )
            
            subprocess.run(mix_cmd, shell=True)
            
            # মিক্সিং যাচাই করুন
            if os.path.exists(mixed_audio) and os.path.getsize(mixed_audio) > 1000:
                final_audio = mixed_audio
                
                # মিক্সড অডিও যাচাই করুন
                try:
                    mixed_duration = float(
                        subprocess.check_output(
                            f'ffprobe -i "{mixed_audio}" -show_entries format=duration -v quiet -of csv="p=0"',
                            shell=True
                        ).decode().strip()
                    )
                    print(f"✅ Successfully mixed audio with BGM: {mixed_duration}s")
                except:
                    print("⚠️ Could not verify mixed audio duration")
            else:
                print("⚠️ Failed to mix with BGM, using original audio")
                final_audio = main_audio
        else:
            print("⚠️ No background music found, using original audio")
            final_audio = main_audio
        
        # সাবটাইটেল তৈরি করুন - প্রতিটি ভিডিওর জন্য আলাদা ইউনিক ফাইলনাম ব্যবহার করুন
        unique_subtitle_id = f"{sanitized_folder_name}_{int(time.time())}"
        temp_subtitle_ass = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.ass")
        
        if use_ai_voice:
            # AI ভয়েসের জন্য সাবটাইটেল তৈরি করুন
            if use_karaoke:
                generate_subtitles_karaoke_chunked(final_audio, temp_subtitle_ass, model, words_per_line=5)
            else:
                # ইউনিক নাম ব্যবহার করুন
                temp_subtitle_srt = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.srt")
                generate_subtitles(final_audio, temp_subtitle_srt, subtitle_format='srt')
                convert_srt_to_ass(temp_subtitle_srt, temp_subtitle_ass, is_short=is_short, position=random.choice(['top', 'bottom', 'left', 'right', 'center']))
        else:
            # নরমাল অডিওর জন্য সাবটাইটেল তৈরি করুন
            if use_karaoke:
                generate_subtitles_karaoke_chunked(final_audio, temp_subtitle_ass, model, words_per_line=5)
            else:
                # ইউনিক নাম ব্যবহার করুন
                temp_subtitle_srt = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.srt")
                generate_subtitles(final_audio, temp_subtitle_srt, subtitle_format='srt')
                convert_srt_to_ass(temp_subtitle_srt, temp_subtitle_ass, is_short=is_short, position=random.choice(['top', 'bottom', 'left', 'right', 'center']))

        # ভিডিও, অডিও এবং সাবটাইটেল একত্রিত করুন
        subtitle_path = os.path.abspath(temp_subtitle_ass).replace("\\", "/").replace(":", "\\:")
        
        print(f"🔊 Final audio path: {final_audio}")
        print(f"🎥 Using video: {used_video}")
        print(f"📄 Using subtitle: {subtitle_path}")
        
        merge_cmd = (
            f'ffmpeg -i "{used_video}" -i "{final_audio}" '
            f'-map 0:v -map 1:a '
            f'-vf "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill,ass=\'{subtitle_path}\'" '
            f'-c:v libx264 -c:a aac -b:a 256k -preset fast -crf 18 -r 30 "{output_video}" -y'
        )
        
        print(f"📝 Running final merge command...")
        subprocess.run(merge_cmd, shell=True)

        # ফাইনাল ভিডিও ফাইল নাম তৈরি করুন
        final_video_path = os.path.join(video_folder, f"{sanitized_folder_name}.mp4")
        
        # আউটপুট ভিডিও থেকে ফাইনাল ভিডিও পাথে মুভ করুন
        os.rename(output_video, final_video_path)
        
        # যাচাই করুন ফাইনাল ভিডিওতে অডিও আছে কিনা
        try:
            audio_check_cmd = f'ffprobe -i "{final_video_path}" -show_streams -select_streams a -loglevel error'
            audio_result = subprocess.run(audio_check_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if audio_result.stdout.strip():
                print(f"✅ Final video has audio track: {final_video_path}")
            else:
                print(f"⚠️ WARNING: Final video may not have audio track: {final_video_path}")
        except Exception as e:
            print(f"⚠️ Could not check final video audio: {e}")
            
        print(f"✅ Final Video Created: {final_video_path}")
        
        # টেক্সট আউটপুট ফাইল তৈরি করুন
        # Whisper এর মাধ্যমে অডিও থেকে ট্রান্সক্রিপ্ট করা
        transcribe = transcribe_audio(audio_file)
        if transcribe:
            # ভিডিও টাইটেল অনুযায়ী আউটপুট ফাইল নাম তৈরি করা
            output_text_path = os.path.join(video_folder, f"{sanitized_folder_name}_output.txt")
            # Azure OpenAI API দিয়ে আউটপুট তৈরি করা
            generate_output_from_azure(transcribe, original_folder_name, output_text_path)
        
        # ভিডিও তৈরি শেষে মেটাডেটা আপডেট করতে কল করুন
        if process_video_metadata(final_video_path):
            print("Metadata update was successful.")
        else:
            print("❌ Failed to update metadata.")
        
        print(f"✅ Video and text saved to: {video_folder}")

        # AI ভয়েস ফাইল ডিলিট করুন (ঐচ্ছিক)
        if use_ai_voice and final_audio != audio_file and os.path.exists(final_audio):
            os.remove(final_audio)
            print(f"🗑️ Deleted AI voice file: {final_audio}")
            
        # সবশেষে ভিডিও-স্পেসিফিক টেম্প ফোল্ডার ডিলিট করুন
        try:
            shutil.rmtree(video_specific_temp)
            print(f"🗑️ Cleaned up temporary folder: {video_specific_temp}")
        except Exception as e:
            print(f"⚠️ Could not clean up temp folder: {e}")

        return True  # Return True if video creation is successful

    except Exception as e:
        print(f"❌ Error creating video for {audio_file}: {e}")
        print(f"⚠️ Full error message: {e}")  # ত্রুটির বিস্তারিত বার্তা দেখাও
        print("⚠️ Skipping this audio and moving to the next one...")
        return False

def process_audio_in_parallel(audio_file, is_short=False, prefix='', suffix='', use_ai_voice=False, use_face_footage=False):
    """একটি অডিও ফাইল প্রসেস করে (নরমাল বা শর্টস) প্যারালেল থ্রেডে চালায়।"""
    try:
        audio_name = os.path.splitext(os.path.basename(audio_file))[0]
        audio_temp_folder = os.path.join(TEMP_FOLDER, audio_name)
        os.makedirs(audio_temp_folder, exist_ok=True)
        output_video = get_output_filename(audio_file, is_short, prefix, suffix)
        
        # AI ভয়েসের জন্য উন্নত চাংক-ভিত্তিক ট্রান্সক্রিপশন ব্যবহার করুন
        if use_ai_voice:
            print("🎙️ Using enhanced chunked transcription for AI voice generation...")
            
            # শর্টস ভিডিও এবং লং ভিডিও উভয়ের জন্য একই উন্নত পদ্ধতি
            ai_voice_file = process_long_audio_with_chunked_transcription(audio_file, audio_temp_folder)
            
            if ai_voice_file and os.path.exists(ai_voice_file):
                print(f"✅ AI voice generation successful using chunked transcription")
                final_audio = ai_voice_file
            else:
                print("❌ AI voice generation failed, using original audio")
                # ব্যাকগ্রাউন্ড মিউজিক রিমুভ করুন
                filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
                remove_background_music(audio_file, filtered_audio, audio_temp_folder)
                final_audio = filtered_audio
                
        else:
            # রেগুলার ভয়েসের জন্য (পুরানো পদ্ধতি)
            # শর্টস ভিডিওগুলোর জন্য সরাসরি প্রসেস করুন
            if is_short:
                filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
                remove_background_music(audio_file, filtered_audio, audio_temp_folder)
                final_audio = filtered_audio
            else:
                # লম্বা ভিডিওগুলোর জন্য চাঙ্ক প্রসেস ব্যবহার করুন
                print("🔄 Checking if audio needs chunk processing...")
                final_audio = process_long_audio_in_chunks(audio_file, audio_temp_folder, use_ai_voice=False)
                
                if not final_audio:
                    print("❌ Failed to process audio in chunks, trying direct processing")
                    filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
                    remove_background_music(audio_file, filtered_audio, audio_temp_folder)
                    final_audio = filtered_audio
        
        # অডিও দিয়ে ভিডিও তৈরি করুন
        success = create_video(STOCK_VIDEO, final_audio, output_video, is_short=is_short, use_karaoke=True, 
                  temp_folder=audio_temp_folder, use_ai_voice=use_ai_voice, use_face_footage=use_face_footage)

        # প্রসেসিং শেষে অডিও এবং টেম্প ফোল্ডার পরিষ্কার করুন
        clear_audio_and_temp_folders(audio_file, TEMP_FOLDER)
        
        return success
    
    except Exception as e:
        print(f"❌ Error in process_audio_in_parallel: {e}")
        return False
       
def get_audio_from_old_audio():
    """old_audio ফোল্ডার থেকে mp3, wav, বা m4a ফাইল লোড করে এবং সেনিটাইজ করে"""
    if not os.path.isdir(OLD_AUDIO_FOLDER):
        return []
        
    # সব অডিও ফাইল সংগ্রহ করুন
    audio_files = glob(os.path.join(OLD_AUDIO_FOLDER, "*.mp3")) + \
                 glob(os.path.join(OLD_AUDIO_FOLDER, "*.wav")) + \
                 glob(os.path.join(OLD_AUDIO_FOLDER, "*.m4a"))
                 
    sanitized_files = []
    
    # প্রতিটি ফাইলের নাম সেনিটাইজ করুন
    for file_path in audio_files:
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # ফাইল নাম সেনিটাইজ করুন
        sanitized_name, original_name = sanitize_filename(file_name)
        sanitized_path = os.path.join(file_dir, sanitized_name)
        
        # যদি ফাইলনাম পরিবর্তন হয়ে থাকে, তাহলে রিনেম করুন
        if sanitized_name != file_name:
            try:
                # ফাইল রিনেম করুন
                os.rename(file_path, sanitized_path)
                print(f"✅ Renamed: {file_name} -> {sanitized_name}")
                
                # ম্যাপিং সংরক্ষণ করুন
                map_filename(file_path, sanitized_path)
                sanitized_files.append(sanitized_path)
            except Exception as e:
                print(f"❌ Error renaming file {file_name}: {e}")
                sanitized_files.append(file_path)  # অরিজিনাল ফাইল ব্যবহার করুন
        else:
            # ফাইলনাম পরিবর্তন না হলেও ম্যাপিং রাখুন
            map_filename(file_path, file_path)
            sanitized_files.append(file_path)
                
    return sanitized_files

# def process_clone_voice_audio(audio_file, temp_folder):
#     """
#     Audio file থেকে ট্রান্সক্রিপ্ট করে এবং ক্লোন ভয়েস জেনারেট করে।
#     """
#     audio_name = os.path.splitext(os.path.basename(audio_file))[0]
    
#     # ট্রান্সক্রিপ্ট করুন
#     transcript = transcribe_audio(audio_file)
    
#     if not transcript:
#         print(f"❌ Failed to transcribe {audio_file}")
#         return None
    
#     print(f"✅ Transcription completed for {audio_name}")
    
#     # ক্লোন ভয়েস জেনারেট করুন
#     cloned_audio = generate_cloned_voice_from_transcript(
#         transcript=transcript,
#         clone_audio_folder=CLONE_AUDIO_FOLDER,
#         output_folder=temp_folder,
#         language="en"  # বাংলা ভাষার জন্য
#     )
    
#     if not cloned_audio:
#         print(f"❌ Failed to generate cloned voice for {audio_name}")
#         return None
    
#     print(f"✅ Generated cloned voice for {audio_name}")
#     return cloned_audio


def batch_process():
    """
    সকল URL ফাইল এবং old_audio ফোল্ডারের ফাইলগুলো প্রসেস করে।
    আপডেটেড: আরও নির্ভরযোগ্য এরর হ্যান্ডলিং এবং মাস্টার URL প্রসেসর ব্যবহার করা হয়েছে।
    """
    # প্রয়োজনীয় ফোল্ডার চেক করুন
    print("\n🔹 গুরুত্বপূর্ণ ফোল্ডারগুলো চেক করা হচ্ছে:")
    critical_folders = [
        {"path": BACKGROUND_MUSIC_FOLDER, "name": "ব্যাকগ্রাউন্ড মিউজিক ফোল্ডার", "extensions": ["*.mp3", "*.wav"]},
        {"path": STOCK_VIDEOS_FOLDER, "name": "স্টক ভিডিও ফোল্ডার", "extensions": ["*.mp4", "*.mov"]},
        {"path": SHORTS_STOCK_VIDEOS_FOLDER, "name": "শর্টস স্টক ভিডিও ফোল্ডার", "extensions": ["*.mp4", "*.mov"]},
        {"path": REAL_FOOTAGE_SHORTS_FOLDER, "name": "রিয়েল ফুটেজ শর্টস ফোল্ডার", "extensions": ["*.mp4", "*.mov"]},
        {"path": REAL_FOOTAGE_LONG_FOLDER, "name": "রিয়েল ফুটেজ লং ফোল্ডার", "extensions": ["*.mp4", "*.mov"]}
    ]
    
    for folder_info in critical_folders:
        path = folder_info["path"]
        name = folder_info["name"]
        extensions = folder_info["extensions"]
        
        print(f"\n🔍 চেক করা হচ্ছে: {name} ({path})")
        
        if not os.path.exists(path):
            print(f"❌ ফোল্ডার খুঁজে পাওয়া যায়নি: {path}")
            print(f"✅ ফোল্ডার তৈরি করা হচ্ছে...")
            os.makedirs(path, exist_ok=True)
        
        # ফাইল সংখ্যা গণনা
        all_files = []
        for ext in extensions:
            all_files.extend(glob(os.path.join(path, ext)))
        
        if all_files:
            print(f"✅ {len(all_files)}টি ফাইল পাওয়া গেছে: {[os.path.basename(f) for f in all_files[:5]]} {'...' if len(all_files) > 5 else ''}")
        else:
            print(f"⚠️ কোনো ফাইল পাওয়া যায়নি। ফোল্ডারে ফাইল যোগ করুন: {path}")
    
    # অস্থায়ী ফোল্ডার পরিষ্কার করুন
    clear_temp_folder()
    
    # old_audio ফোল্ডার থেকে ফাইলগুলো নিয়ে আসুন
    old_audio_files = get_audio_from_old_audio()
    
    # যদি old_audio ফোল্ডারে কোনো ফাইল থাকে
    if old_audio_files:
        print(f"\n🔹 old_audio ফোল্ডার থেকে {len(old_audio_files)}টি ফাইল পাওয়া গেছে। এগুলো প্রসেস করা হচ্ছে:")
        
        success_count = 0
        fail_count = 0
        
        for idx, audio_file in enumerate(old_audio_files, 1):
            video_title = os.path.splitext(os.path.basename(audio_file))[0]
            print(f"\n🎵 প্রসেসিং ({idx}/{len(old_audio_files)}): {video_title}")
            
            try:
                result = process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=False, use_face_footage=False)
                if result:
                    success_count += 1
                    print(f"✅ সফলভাবে ভিডিও তৈরি হয়েছে: {video_title}")
                else:
                    fail_count += 1
                    print(f"❌ ভিডিও তৈরি করতে ব্যর্থ: {video_title}")
            except Exception as e:
                fail_count += 1
                print(f"❌ অডিও প্রসেস করতে এরর: {e}")
        
        print(f"\n🔹 old_audio ফোল্ডার প্রসেসিং সম্পন্ন: {success_count}টি সফল, {fail_count}টি ব্যর্থ")
    
    # YouTube URL ফাইলগুলো প্রসেস করুন
    else:
        print("\n🔹 old_audio ফোল্ডারে কোনো ফাইল নেই। YouTube URL ফাইলগুলো প্রসেস করা হচ্ছে...")
        
        # ফেস ফুটেজ ফাইল সংখ্যা চেক করুন (যদি ফেস ফুটেজ ব্যবহার করতে হয়)
        face_file_counts = face_handler.check_face_footage_files()
        
        # মাস্টার URL প্রসেসর ব্যবহার করে সব URL একসাথে প্রসেস করুন
        process_all_url_files()
    
    print("\n🎉 সমস্ত ভিডিও প্রসেসিং সম্পন্ন হয়েছে!")
    
if __name__ == "__main__":
    print("\n" + "="*80)
    print(f"🚀 YouTube ভিডিও প্রসেসিং সিস্টেম শুরু হচ্ছে...")
    print(f"📂 বেস পাথ: {BASE_PATH}")
    print("="*80 + "\n")

    print("⏳ Whisper মডেল লোড করা হচ্ছে...")
    
    try:
        # ডিভাইস চেকিং এবং মডেলকে ডিভাইসে পাঠানো
        if torch.cuda.is_available():
            device = torch.device("cuda")
            print(f"✅ CUDA ডিভাইস পাওয়া গেছে: {torch.cuda.get_device_name(0)}")
        else:
            device = torch.device("cpu")
            print(f"⚠️ CUDA ডিভাইস পাওয়া যায়নি, CPU ব্যবহার করা হচ্ছে")
        
        # Whisper মডেল লোড করা
        model = whisper.load_model("small")
        
        # মডেলকে GPU বা CPU তে পাঠানো
        model.to(device)
        print("✅ Whisper মডেল সফলভাবে লোড হয়েছে!")
        
        # মেইন ব্যাচ প্রসেসিং ফাংশন কল করুন
        batch_process()
        
    except Exception as e:
        print(f"❌ প্রোগ্রাম চালাতে এরর: {e}")
        print("দয়া করে চেক করুন:")
        print("1. সব প্রয়োজনীয় ফোল্ডার আছে কিনা")
        print("2. URL ফাইলগুলোতে সঠিক লিংক আছে কিনা")
        print("3. ffmpeg ঠিকমতো ইনস্টল করা আছে কিনা")
        print("4. সব মডিউল ইনস্টল করা আছে কিনা (pip install -r requirements.txt)")
    
    finally:
        print("\n🧹 কিছু অস্থায়ী ফাইল থাকলে পরিষ্কার করা হচ্ছে...")
        try:
            clear_temp_folder()
            print("✅ অস্থায়ী ফোল্ডার পরিষ্কার করা হয়েছে")
        except:
            pass
        
        print("\n👋 প্রোগ্রাম শেষ হয়েছে।")