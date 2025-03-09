import os
import json
import requests
from dotenv import load_dotenv
import win32com.client  # For interacting with file properties in Windows
import re
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TIT2, TPE1, TALB, COMM

# .env ফাইল থেকে Azure OpenAI API সেটআপ লোড করুন
load_dotenv()

# Azure OpenAI API কনফিগারেশন
endpoint = os.getenv("ENDPOINT_URL", "https://et1.openai.azure.com/")  
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o")
api_key = os.getenv("API_KEY")


def log_to_file(message):
    """Helper function to log messages to a file"""
    log_file = "api_logs.txt"  # Direct file path
    try:
        with open(log_file, "a", encoding='utf-8') as f:
            f.write(message + "\n")
        print(f"Log written: {message}")  # To verify the log
    except Exception as e:
        print(f"Error writing log: {e}")  # Handle any errors in logging


def generate_title_from_azure(video_title):
    """Azure OpenAI API দিয়ে ইউটিউব ভিডিও টাইটেল জেনারেট করুন"""
    prompt = f"""
    Video Title: {video_title}
    1. Provide an engaging YouTube video title without double quotation. Do not add double quotation, Just give me plain text.
    """
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI that helps create engaging YouTube content."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result
        else:
            log_to_file(f"❌ API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        log_to_file(f"❌ Error: {e}")
        return None


def generate_subtitle_from_azure(video_title):
    """Azure OpenAI API দিয়ে ভিডিও সাবটাইটেল (দুটি প্যারাগ্রাফ) জেনারেট করুন"""
    prompt = f"""
    Video Title: {video_title}
    1. Write 2 line sentence based on the video content. without double quotation. Do not add double quotation, Just give me plain text.
    """
    
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI that helps generate video subtitles."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result
        else:
            log_to_file(f"❌ API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        log_to_file(f"❌ Error: {e}")
        return None


def generate_hashtags_from_azure(video_title):
    """Azure OpenAI API দিয়ে ভিডিওর জন্য হ্যাশট্যাগ জেনারেট করুন"""
    prompt = f"""
    Video Title: {video_title}
    1. Write 10 hashtags relevant to the video.
    """
    
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI that helps generate hashtags for social media."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result
        else:
            log_to_file(f"❌ API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        log_to_file(f"❌ Error: {e}")
        return None


def generate_tags_from_azure(video_title):
    """Azure OpenAI API দিয়ে ভিডিওর জন্য ট্যাগ জেনারেট করুন"""
    prompt = f"""
    Video Title: {video_title}
    1. Write 10 tags separated by commas.
    """
    
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI that helps generate tags for videos."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result
        else:
            log_to_file(f"❌ API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        log_to_file(f"❌ Error: {e}")
        return None


def generate_description_from_azure(video_title):
    """Azure OpenAI API দিয়ে ভিডিওর জন্য বর্ণনা (দুটি প্যারাগ্রাফ) জেনারেট করুন"""
    prompt = f"""
    Video Title: {video_title}
    1. Generate 2 paragraphs for the video description.
    """
    
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {
        "messages": [
            {"role": "system", "content": "You are an AI that helps generate video descriptions."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"].strip()
            return result
        else:
            log_to_file(f"❌ API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        log_to_file(f"❌ Error: {e}")
        return None


def set_file_properties(file_path, title=None, subtitle=None, tags=None, hashtags=None, description=None, rating="5.0"):
    """ফাইলের মেটাডেটা আপডেট করা (Title, Subtitle, Tags, Hashtags, Description)"""
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File path does not exist: {file_path}")
        
        if file_path.lower().endswith(".mp4"):
            # MP4 ফাইলের মেটাডেটা আপডেট করা
            audio = MP4(file_path)
            
            if title:
                audio["\xa9nam"] = title  # Title (track name)
            if subtitle:
                audio["\xa9alb"] = subtitle  # Subtitle (Album name)
            if tags:
                audio["\xa9gen"] = tags  # Tags (genre)
            if description:
                audio["\xa9cmt"] = description  # Comments (Description)
            
            audio.save()
            print(f"✅ Metadata updated for {file_path} (MP4)")

        elif file_path.lower().endswith(".mp3"):
            # MP3 ফাইলের মেটাডেটা আপডেট করা
            audio = ID3(file_path)
            
            if title:
                audio.add(TIT2(encoding=3, text=title))  # Title (track name)
            if subtitle:
                audio.add(TALB(encoding=3, text=subtitle))  # Subtitle (Album name)
            if tags:
                audio.add(TPE1(encoding=3, text=tags))  # Tags (artist)
            if description:
                audio.add(COMM(encoding=3, lang="eng", desc="Description", text=description))  # Comments (Description)
            
            audio.save()
            print(f"✅ Metadata updated for {file_path} (MP3)")

        # Update Rating for file (using Windows Shell)
        shell = win32com.client.Dispatch("Shell.Application")
        folder = shell.Namespace(os.path.dirname(file_path))
        file_item = folder.ParseName(os.path.basename(file_path))

        if file_item is None:
            print(f"❌ Unable to parse file: {file_path}")
            return

        folder.GetDetailsOf(file_item, 39).Value = rating  # "Rating" column index
        print(f"✅ Rating set for {file_path} as {rating} stars")
    except Exception as e:
        print(f"❌ Error updating metadata for {file_path}: {e}")
        log_to_file(f"❌ Error updating metadata for {file_path}: {e}")


def process_video_metadata(video_file_path):
    """ভিডিও ফাইলের মেটাডেটা আপডেট করা"""
    video_file_name = os.path.splitext(os.path.basename(video_file_path))[0]
    print(f"Processing video: {video_file_name}...")

    # Generate metadata using Azure OpenAI
    title = generate_title_from_azure(video_file_name)
    subtitle = generate_subtitle_from_azure(video_file_name)
    hashtags = generate_hashtags_from_azure(video_file_name)
    tags = generate_tags_from_azure(video_file_name)
    description = generate_description_from_azure(video_file_name)

    # Update video file properties if metadata was generated
    if title or subtitle or tags or hashtags or description:
        set_file_properties(video_file_path, title=title, subtitle=subtitle, tags=tags, hashtags=hashtags, description=description)
        print(f"✅ Metadata update successful for {video_file_name}")
    else:
        print(f"❌ Failed to generate metadata for {video_file_name}")


