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


# 🔹 কনফিগারেশন
BASE_PATH = "G:/video_project/"
OLD_AUDIO_FOLDER = "G:/video_project/old_audio"
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
# 🔹 ফেস ফুটেজ ফোল্ডার কনফিগারেশন
REAL_FOOTAGE_SHORTS_FOLDER = os.path.join(BASE_PATH, "real_footage_shorts")
REAL_FOOTAGE_LONG_FOLDER = os.path.join(BASE_PATH, "real_footage_long")
YOUTUBE_SHORTS_WITH_FACE_URL_FILE = os.path.join(BASE_PATH, "youtube_shorts_with_5_sec_with_face.txt")
YOUTUBE_LONG_WITH_FACE_URL_FILE = os.path.join(BASE_PATH, "youtube_long_with_5_sec_with_face.txt")
YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE = os.path.join(BASE_PATH, "youtube_shorts_with_5_sec_with_face_ai.txt")
YOUTUBE_LONG_WITH_FACE_AI_URL_FILE = os.path.join(BASE_PATH, "youtube_long_with_5_sec_with_face_ai.txt")

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


def get_random_file(folder_path, extensions=(".mp4", ".mov", ".mp3", ".wav")):
    """ফোল্ডার থেকে নির্দিষ্ট এক্সটেনশনের র্যান্ডম ফাইল পেতে সাহায্য করে।"""
    if not os.path.isdir(folder_path):
        return None
    file_list = [f for f in glob(os.path.join(folder_path, "*")) if f.lower().endswith(extensions)]
    if file_list:
        return random.choice(file_list)
    return None


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


def convert_srt_to_ass(srt_file, ass_file, is_short=False):
    """Convert SRT subtitles to ASS format with premium styling and random color patterns."""
    try:
        # ফাইলনাম এক্সট্রাক্ট করুন
        base_filename = os.path.basename(srt_file)
        
        print(f"\n🎨 Creating design for: {base_filename}")
        
        subs = pysubs2.load(srt_file, encoding="utf-8")
        
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
    """Download YouTube audio as MP3 and sanitize filenames."""
    if not os.path.isfile(url_file):
        return []
    with open(url_file, "r", encoding="utf-8") as file:
        urls = [line.strip() for line in file.readlines() if line.strip()]
    if not urls:
        return []

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(AUDIO_FOLDER, '%(title)s.%(ext)s'),
        'noplaylist': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)
    
    # ডাউনলোড করা ফাইলগুলো সংগ্রহ করুন
    downloaded_files = glob(os.path.join(AUDIO_FOLDER, "*.mp3"))
    sanitized_files = []
    
    # প্রতিটি ফাইলের নাম সেনিটাইজ করুন
    for file_path in downloaded_files:
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
    
    print(f"✅ YouTube MP3 Download Complete from {url_file}!")
    return sanitized_files

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
            print("Running Spleeter for voice separation...")
            subprocess.run(spleeter_cmd, shell=True, timeout=300)  # 5 মিনিট টাইমআউট
            
            # Spleeter আউটপুট পাথ - অডিও নাম অনুযায়ী ফোল্ডার তৈরি করে
            audio_name = os.path.splitext(os.path.basename(input_audio))[0]
            vocals_path = os.path.join(spleeter_output, audio_name, "vocals.wav")
            
            if os.path.exists(vocals_path):
                # ভয়েস কোয়ালিটি উন্নত করুন
                enhance_cmd = (
                    f'ffmpeg -i "{vocals_path}" -af "volume=1.8, ' 
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
            "highpass=f=80, " +           # নিচু আওয়াজ বাদ দিন
            "lowpass=f=8000, " +          # উচ্চ আওয়াজ বাদ দিন
            "volume=2.0, " +              # ভলিউম বাড়ান
            "compand=attacks=0.01:decays=0.1:" +  # ডাইনামিক কম্প্রেশন
            "points=-80/-80|-45/-45|-27/-25|-15/-10|-5/-2|0/0|20/8"
        )
        
        ffmpeg_cmd = (
            f'ffmpeg -i "{input_audio}" -af "{audio_filter}" '
            f'-c:a pcm_s16le "{output_audio}" -y'
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

def color_line_dynamically(line, color1="&H00FF00&", color2="&HFFFFFF&", ratio=0.7):
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

def create_karaoke_line(words, line_start, line_end):
    """
    words: [{'start': float, 'end': float, 'word': string}, ...]
    line_start, line_end: পুরো লাইনের শুরু ও শেষ সময় (সেকেন্ডে)
    রিটার্ন: \k ট্যাগসহ একটি স্ট্রিং, যাতে শব্দগুলোর উচ্চারণকাল অনুযায়ী হাইলাইট হয়।
    """
    karaoke_text = ""
    for w in words:
        w_start = w["start"] - line_start
        w_end = w["end"] - line_start
        duration_sec = max(0, w_end - w_start)
        duration_cs = int(duration_sec * 100)
        karaoke_text += f"{{\\k{duration_cs}}}{w['word']} "
    karaoke_text += "{\\k0}"
    return karaoke_text.strip()

def split_into_chunks_karaoke(result, words_per_line=5):
    """
    Whisper result থেকে word-level তথ্য নিয়ে প্রতিটি চাঙ্ককে (প্রতি words_per_line টি ওয়ার্ড বা যতি চিহ্নে)
    একটি করে "ক্যারাওকে লাইন" হিসেবে রিটার্ন করে।
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
            current_words.append(w)
            if (len(current_words) >= words_per_line) or any(punct in w["word"] for punct in [".", "!", "?", ","]):
                karaoke_line = create_karaoke_line(current_words, chunk_start_time, chunk_end_time)
                all_chunks.append({
                    "start": chunk_start_time,
                    "end": chunk_end_time,
                    "text": karaoke_line
                })
                current_words = []
                chunk_start_time = None
                chunk_end_time = None
    if current_words:
        karaoke_line = create_karaoke_line(current_words, chunk_start_time, chunk_end_time)
        all_chunks.append({
            "start": chunk_start_time,
            "end": chunk_end_time,
            "text": karaoke_line
        })
    return all_chunks

def generate_subtitles_karaoke_chunked(audio_file, subtitle_file, words_per_line=5):
    """
    Whisper থেকে word-level timestamps নিয়ে, প্রতি words_per_line ওয়ার্ডে চাঙ্ক করে
    ক্যারাওকে এফেক্ট সহ .ass ফাইল তৈরি করে।
    """
    global model
    # অডিও ফাইল লোড করা
    audio_tensor = whisper.load_audio(audio_file)  # Ensure this is a numpy array first
    audio_tensor = torch.from_numpy(audio_tensor).float().to(device)  # Convert numpy array to tensor and move it to the device
    
    result = model.transcribe(audio_tensor, word_timestamps=True, task='transcribe')
    if not result or "segments" not in result or not result["segments"]:
        print(f"❌ Transcription failed or empty segments for: {audio_file}")
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write("")
        return
    chunks = split_into_chunks_karaoke(result, words_per_line=words_per_line)
    subs = pysubs2.SSAFile()
    fade_tag = r"{\fad(300,300)}"
    for chunk in chunks:
        start_ms = chunk["start"] * 1000
        end_ms = chunk["end"] * 1000
        karaoke_line = chunk["text"]
        karaoke_line = fade_tag + karaoke_line
        karaoke_line = karaoke_line.upper()
        event = pysubs2.SSAEvent(
            start=start_ms,
            end=end_ms,
            text=karaoke_line
        )
        subs.append(event)
    subs.styles["Default"].fontname = "Montserrat"
    subs.styles["Default"].fontsize = 24
    subs.styles["Default"].bold = True
    subs.styles["Default"].alignment = 2
    subs.styles["Default"].outline = 4
    subs.styles["Default"].shadow = 3
    subs.styles["Default"].borderstyle = 1
    subs.styles["Default"].marginv = 60
    subs.styles["Default"].secondarycolor = pysubs2.Color(0, 255, 0, 0)
    subs.save(subtitle_file)
    print(f"✅ Karaoke subtitles (chunked) generated: {subtitle_file}")

def generate_subtitles_karaoke(audio_file, subtitle_file):
    """
    Whisper থেকে word-level timestamps নিয়ে প্রতিটি সেগমেন্টকে ক্যারাওকে এফেক্ট সহ .ass ফাইল তৈরি করে।
    """
    global model
    # অডিও ফাইল লোড করা
    audio_tensor = whisper.load_audio(audio_file)  # Ensure this is a numpy array first
    audio_tensor = torch.from_numpy(audio_tensor).float().to(device)  # Convert numpy array to tensor and move it to the device
    
    result = model.transcribe(audio_tensor, word_timestamps=True, task='transcribe')
    if not result or "segments" not in result or not result["segments"]:
        print(f"❌ Transcription failed or empty segments for: {audio_file}")
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write("")
        return
    subs = pysubs2.SSAFile()
    fade_tag = r"{\fad(300,300)}"
    for seg in result["segments"]:
        seg_start = seg["start"]
        seg_end = seg["end"]
        words = seg["words"]
        if not words:
            continue
        karaoke_line = create_karaoke_line(words, seg_start, seg_end)
        karaoke_line = fade_tag + karaoke_line
        karaoke_line = karaoke_line.upper()
        event = pysubs2.SSAEvent(
            start=seg_start * 1000,
            end=seg_end * 1000,
            text=karaoke_line
        )
        subs.append(event)
    subs.styles["Default"].fontname = "Montserrat"
    subs.styles["Default"].fontsize = 22
    subs.styles["Default"].bold = True
    subs.styles["Default"].alignment = 2
    subs.styles["Default"].outline = 4
    subs.styles["Default"].shadow = 3
    subs.styles["Default"].borderstyle = 1
    subs.styles["Default"].marginv = 60
    subs.styles["Default"].secondarycolor = pysubs2.Color(0, 255, 0, 0)
    karaoke_style = subs.styles["Default"].copy()
    karaoke_style.primarycolor = pysubs2.Color(255, 255, 255, 0)
    karaoke_style.secondarycolor = pysubs2.Color(255, 255, 0, 0)
    subs.styles["Karaoke"] = karaoke_style
    subs.save(subtitle_file)
    print(f"✅ Karaoke subtitles generated: {subtitle_file}")

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
                    
                    # AI ভয়েসের সাথে ব্যাকগ্রাউন্ড মিউজিক মিক্স করুন
                    bgm_file = get_random_file(BACKGROUND_MUSIC_FOLDER, (".mp3", ".wav"))
                    if bgm_file:
                        mixed_audio = os.path.join(video_specific_temp, "mixed_audio.m4a")
                        
                        # উন্নত মিক্সিং ফিল্টার:
                        # 1. ব্যাকগ্রাউন্ড মিউজিকের ভলিউম আরো কমিয়ে দেওয়া (0.1 থেকে 0.05)
                        # 2. স্পিচ ভলিউম বাড়ানো (1.5x)
                        # 3. মিক্সিং এর সময় ওয়েটেজ পরিবর্তন (স্পিচকে অগ্রাধিকার দেওয়া)
                        mix_cmd = (
                            f'ffmpeg -i "{ai_voice_file}" -i "{bgm_file}" -filter_complex '
                            f'"[0:a]volume=1.5[speech];'
                            f'[1:a]aloop=loop=-1:size=2*44100*60,volume=0.05[music];'
                            f'[speech][music]amix=inputs=2:duration=first:weights=10 1:dropout_transition=3" '
                            f'-c:a aac -b:a 192k "{mixed_audio}" -y'
                        )
                        
                        subprocess.run(mix_cmd, shell=True)
                        
                        # যাচাই করুন যে মিক্স সফল হয়েছে
                        if os.path.exists(mixed_audio) and os.path.getsize(mixed_audio) > 0:
                            print(f"✅ Mixed audio with enhanced speech volume and reduced background music")
                            final_audio = mixed_audio
                        else:
                            print(f"⚠️ Failed to mix audio, using original AI voice")
                            final_audio = ai_voice_file
                    else:
                        final_audio = ai_voice_file
                        print("⚠️ No background music found, using AI voice without music")
                else:
                    print("❌ AI voice generation failed, using original audio")
                    final_audio = audio_file
            else:
                print("❌ Transcription failed, using original audio")
                final_audio = audio_file
        else:
            # ব্যাকগ্রাউন্ড মিউজিক মিক্স করুন (যদি AI ভয়েস না হয়)
            # ব্যাকগ্রাউন্ড মিউজিক মিক্সিং অংশ আপডেট করুন (যদি AI ভয়েস না হয়)
            bgm_file = get_random_file(BACKGROUND_MUSIC_FOLDER, (".mp3", ".wav"))
            if bgm_file:
                mixed_audio = os.path.join(video_specific_temp, "mixed_audio.m4a")
                
                # উন্নত মিক্সিং ফিল্টার:
                # 1. ব্যাকগ্রাউন্ড মিউজিকের ভলিউম আরো কমিয়ে দেওয়া (0.1 থেকে 0.05)
                # 2. স্পিচ ভলিউম বাড়ানো (1.5x)
                # 3. মিক্সিং এর সময় ওয়েটেজ পরিবর্তন (স্পিচকে অগ্রাধিকার দেওয়া)
                mix_cmd = (
                    f'ffmpeg -i "{audio_file}" -i "{bgm_file}" -filter_complex '
                    f'"[0:a]volume=1.5[speech];'
                    f'[1:a]aloop=loop=-1:size=2*44100*60,volume=0.05[music];'
                    f'[speech][music]amix=inputs=2:duration=first:weights=10 1:dropout_transition=3" '
                    f'-c:a aac -b:a 192k "{mixed_audio}" -y'
                )
                
                subprocess.run(mix_cmd, shell=True)
                
                # যাচাই করুন যে মিক্স সফল হয়েছে
                if os.path.exists(mixed_audio) and os.path.getsize(mixed_audio) > 0:
                    print(f"✅ Mixed audio with enhanced speech volume and reduced background music")
                    final_audio = mixed_audio
                else:
                    print(f"⚠️ Failed to mix audio, using original enhanced audio")
                    final_audio = audio_file
            else:
                final_audio = audio_file

        # অডিও ডিউরেশন চেক করুন
        audio_duration = float(
            subprocess.check_output(
                f'ffprobe -i "{final_audio}" -show_entries format=duration -v quiet -of csv="p=0"',
                shell=True
            ).decode().strip()
        )
        short_duration = min(audio_duration, 60) if is_short else audio_duration
        print(f"📊 Final audio duration: {short_duration:.2f}s")
        
        # ফেস ফুটেজ প্রসেসিং
        # এই অংশটি create_video ফাংশনের ভিতরে রাখুন, যেখানে ফেস ফুটেজ প্রসেস করা হয়

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
        
        # সাবটাইটেল তৈরি করুন - প্রতিটি ভিডিওর জন্য আলাদা ইউনিক ফাইলনাম ব্যবহার করুন
        unique_subtitle_id = f"{sanitized_folder_name}_{int(time.time())}"
        temp_subtitle_ass = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.ass")
        
        if use_ai_voice:
            # AI ভয়েসের জন্য সাবটাইটেল তৈরি করুন
            if use_karaoke:
                generate_subtitles_karaoke_chunked(final_audio, temp_subtitle_ass, words_per_line=5)
            else:
                # ইউনিক নাম ব্যবহার করুন
                temp_subtitle_srt = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.srt")
                generate_subtitles(final_audio, temp_subtitle_srt, subtitle_format='srt')
                convert_srt_to_ass(temp_subtitle_srt, temp_subtitle_ass, is_short=is_short)
        else:
            # নরমাল অডিওর জন্য সাবটাইটেল তৈরি করুন
            if use_karaoke:
                generate_subtitles_karaoke_chunked(final_audio, temp_subtitle_ass, words_per_line=5)
            else:
                # ইউনিক নাম ব্যবহার করুন
                temp_subtitle_srt = os.path.join(video_specific_temp, f"subtitles_{unique_subtitle_id}.srt")
                generate_subtitles(final_audio, temp_subtitle_srt, subtitle_format='srt')
                convert_srt_to_ass(temp_subtitle_srt, temp_subtitle_ass, is_short=is_short)

        # ভিডিও, অডিও এবং সাবটাইটেল একত্রিত করুন
        subtitle_path = os.path.abspath(temp_subtitle_ass).replace("\\", "/").replace(":", "\\:")
        merge_cmd = (
            f'ffmpeg -i "{used_video}" -i "{final_audio}" '
            f'-map 0:v -map 1:a '
            f'-vf "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill,ass=\'{subtitle_path}\'" '
            f'-c:v libx264 -c:a aac -preset fast -crf 18 -r 30 "{output_video}" -y'
        )
        subprocess.run(merge_cmd, shell=True)

        # ফাইনাল ভিডিও ফাইল নাম তৈরি করুন
        final_video_path = os.path.join(video_folder, f"{sanitized_folder_name}.mp4")
        
        # আউটপুট ভিডিও থেকে ফাইনাল ভিডিও পাথে মুভ করুন
        os.rename(output_video, final_video_path)
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
    audio_name = os.path.splitext(os.path.basename(audio_file))[0]
    
    audio_temp_folder = os.path.join(TEMP_FOLDER, audio_name)
    os.makedirs(audio_temp_folder, exist_ok=True)
    filtered_audio = os.path.join(audio_temp_folder, f"{audio_name}_filtered.wav")
    
    output_video = get_output_filename(audio_file, is_short, prefix, suffix)
    
    # অডিও প্রসেসিং
    remove_background_music(audio_file, filtered_audio, audio_temp_folder)
    
    # AI ভয়েস জেনারেট করা (যদি use_ai_voice=True হয়)
    final_audio = filtered_audio
    transcript = ""
    
    if use_ai_voice:
        print("🎙️ Transcribing audio for AI voice generation...")
        transcript = transcribe_audio(filtered_audio)
        
        if transcript:
            # AI ভয়েস জেনারেট করুন
            ai_voice_file = transcribe_and_generate_ai_voice(transcript, audio_name, audio_temp_folder)
            
            if ai_voice_file and os.path.exists(ai_voice_file):
                print(f"✅ Using AI voice: {ai_voice_file}")
                final_audio = ai_voice_file
                
                # AI ভয়েসের অডিও ডিউরেশন চেক করুন
                try:
                    ai_voice_duration = float(
                        subprocess.check_output(
                            f'ffprobe -i "{ai_voice_file}" -show_entries format=duration -v quiet -of csv="p=0"',
                            shell=True
                        ).decode().strip()
                    )
                    print(f"✅ AI Voice Duration: {ai_voice_duration:.2f} seconds")
                except Exception as e:
                    print(f"⚠️ Could not check AI voice duration: {e}")
    
    # ভিডিও তৈরি করা
    create_video(STOCK_VIDEO, final_audio, output_video, is_short=is_short, use_karaoke=True, 
                temp_folder=audio_temp_folder, use_ai_voice=use_ai_voice, use_face_footage=use_face_footage)

    # Clear the specific audio and temp folder after processing
    clear_audio_and_temp_folders(audio_file, TEMP_FOLDER)
  
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

def batch_process():
    """Process batch of normal and shorts videos one by one with support for AI voice and face footage."""
    clear_temp_folder()
    old_audio_files = get_audio_from_old_audio()  # old_audio ফোল্ডার থেকে ফাইলগুলো নিয়ে আসুন

    # URL লিস্ট ফাইল বোঝার জন্য চেক করুন
    has_ai_voice_shorts = os.path.isfile(YOUTUBE_AI_VOICE_SHORTS_URL_FILE) and os.path.getsize(YOUTUBE_AI_VOICE_SHORTS_URL_FILE) > 0
    has_ai_voice_long = os.path.isfile(YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE) and os.path.getsize(YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE) > 0
    has_regular_shorts = os.path.isfile(YOUTUBE_SHORTS_URL_FILE) and os.path.getsize(YOUTUBE_SHORTS_URL_FILE) > 0
    has_regular_videos = os.path.isfile(YOUTUBE_URL_FILE) and os.path.getsize(YOUTUBE_URL_FILE) > 0
    
    # ফেস ফুটেজ URL ফাইল চেক
    has_face_shorts = os.path.isfile(YOUTUBE_SHORTS_WITH_FACE_URL_FILE) and os.path.getsize(YOUTUBE_SHORTS_WITH_FACE_URL_FILE) > 0
    has_face_long = os.path.isfile(YOUTUBE_LONG_WITH_FACE_URL_FILE) and os.path.getsize(YOUTUBE_LONG_WITH_FACE_URL_FILE) > 0
    has_face_ai_shorts = os.path.isfile(YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE) and os.path.getsize(YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE) > 0
    has_face_ai_long = os.path.isfile(YOUTUBE_LONG_WITH_FACE_AI_URL_FILE) and os.path.getsize(YOUTUBE_LONG_WITH_FACE_AI_URL_FILE) > 0

    # যদি old_audio ফোল্ডারে কোনো ফাইল না থাকে, তবে YouTube থেকে অডিও ডাউনলোড করুন
    if not old_audio_files:
        # ০. ফেস ফুটেজ ফাইল সংখ্যা চেক করুন
        face_file_counts = face_handler.check_face_footage_files()
        
        # ১. ফেস ফুটেজ সহ শর্টস (রেগুলার অডিও)
        if has_face_shorts:
            print("\n🔹 Processing Face Footage Shorts from YouTube:")
            face_shorts = download_youtube_audio(YOUTUBE_SHORTS_WITH_FACE_URL_FILE)
            for audio_file in face_shorts:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing face footage shorts: {video_title}")
                process_audio_in_parallel(audio_file, is_short=True, use_ai_voice=False, use_face_footage=True)
        
        # ২. ফেস ফুটেজ সহ লং ভিডিও (রেগুলার অডিও)
        if has_face_long:
            print("\n🔹 Processing Face Footage Long Videos from YouTube:")
            face_long = download_youtube_audio(YOUTUBE_LONG_WITH_FACE_URL_FILE)
            for audio_file in face_long:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing face footage long video: {video_title}")
                process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=False, use_face_footage=True)
        
        # ৩. ফেস ফুটেজ সহ শর্টস (AI ভয়েস)
        if has_face_ai_shorts:
            print("\n🔹 Processing Face Footage Shorts with AI Voice from YouTube:")
            face_ai_shorts = download_youtube_audio(YOUTUBE_SHORTS_WITH_FACE_AI_URL_FILE)
            for audio_file in face_ai_shorts:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing face footage shorts with AI voice: {video_title}")
                process_audio_in_parallel(audio_file, is_short=True, use_ai_voice=True, use_face_footage=True)
        
        # ৪. ফেস ফুটেজ সহ লং ভিডিও (AI ভয়েস)
        if has_face_ai_long:
            print("\n🔹 Processing Face Footage Long Videos with AI Voice from YouTube:")
            face_ai_long = download_youtube_audio(YOUTUBE_LONG_WITH_FACE_AI_URL_FILE)
            for audio_file in face_ai_long:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing face footage long video with AI voice: {video_title}")
                process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=True, use_face_footage=True)
        
        # ৫. AI ভয়েস লং ভিডিও (ফেস ফুটেজ ছাড়া)
        if has_ai_voice_long:
            print("\n🔹 Processing AI Voice Long Videos from YouTube:")
            ai_voice_long_videos = download_youtube_audio(YOUTUBE_AI_VOICE_LONG_VIDEO_URL_FILE)
            for audio_file in ai_voice_long_videos:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing AI voice long video: {video_title}")
                process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=True, use_face_footage=False)
        
        # ৬. AI ভয়েস শর্টস ভিডিও (ফেস ফুটেজ ছাড়া)
        if has_ai_voice_shorts:
            print("\n🔹 Processing AI Voice Shorts from YouTube:")
            ai_voice_shorts = download_youtube_audio(YOUTUBE_AI_VOICE_SHORTS_URL_FILE)
            for audio_file in ai_voice_shorts:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing AI voice shorts: {video_title}")
                process_audio_in_parallel(audio_file, is_short=True, use_ai_voice=True, use_face_footage=False)
        
        # ৭. রেগুলার লং ভিডিও (ফেস ফুটেজ ছাড়া)
        if has_regular_videos:
            print("\n🔹 Processing Regular Videos from YouTube:")
            normal_audio_files = download_youtube_audio(YOUTUBE_URL_FILE)
            for audio_file in normal_audio_files:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing regular video: {video_title}")
                process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=False, use_face_footage=False)
        
        # ৮. রেগুলার শর্টস ভিডিও (ফেস ফুটেজ ছাড়া)
        if has_regular_shorts:
            print("\n🔹 Processing Regular Shorts from YouTube:")
            shorts_audio_files = download_youtube_audio(YOUTUBE_SHORTS_URL_FILE)
            for audio_file in shorts_audio_files:
                video_title = os.path.splitext(os.path.basename(audio_file))[0]
                print(f"\nProcessing regular shorts: {video_title}")
                process_audio_in_parallel(audio_file, is_short=True, use_ai_voice=False, use_face_footage=False)
    else:
        # যদি old_audio ফোল্ডারে ফাইল থাকে, তবে সেগুলি প্রসেস করুন (এখানে আমরা AI ভয়েস ব্যবহার করছি না)
        normal_audio_files = old_audio_files
        for audio_file in normal_audio_files:
            video_title = os.path.splitext(os.path.basename(audio_file))[0]
            print(f"\nProcessing from old_audio: {video_title}")
            process_audio_in_parallel(audio_file, is_short=False, use_ai_voice=False, use_face_footage=False)
        
    print("\n🎉 All videos are successfully created!")

if __name__ == "__main__":
    print("⏳ Loading Whisper model...")
    
    # ডিভাইস চেকিং এবং মডেলকে ডিভাইসে পাঠানো
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    
    # Whisper মডেল লোড করা
    model = whisper.load_model("small")
    
    # মডেলকে GPU বা CPU তে পাঠানো
    model.to(device)

    print("✅ Whisper model loaded successfully!")
    batch_process()