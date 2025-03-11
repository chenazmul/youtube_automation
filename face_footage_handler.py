#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import random
import subprocess
import glob
import tempfile
import shutil

class FaceFootageHandler:
    """
    রিয়েল ফুটেজ (ফেস ফুটেজ) নিয়ে কাজ করার জন্য একটি ক্লাস।
    এটি শর্টস ও লং ভিডিওর জন্য প্রথম কয়েক সেকেন্ডে ফেস ফুটেজ যোগ করে।
    """
    
    def __init__(self, base_path):
        """
        ইনিশিয়ালাইজার - ফোল্ডার পাথগুলি সেট করে

        Args:
            base_path (str): প্রোজেক্টের মূল ফোল্ডার পাথ
        """
        self.base_path = base_path
        
        # ফেস ফুটেজ ফোল্ডার
        self.real_footage_shorts = os.path.join(base_path, "real_footage_shorts")
        self.real_footage_long = os.path.join(base_path, "real_footage_long")
        
        # ফোল্ডার না থাকলে তৈরি করা
        os.makedirs(self.real_footage_shorts, exist_ok=True)
        os.makedirs(self.real_footage_long, exist_ok=True)
        
        # URL ফাইলগুলির পাথ
        self.shorts_with_face_url_file = os.path.join(base_path, "youtube_shorts_with_5_sec_with_face.txt")
        self.long_with_face_url_file = os.path.join(base_path, "youtube_long_with_5_sec_with_face.txt")
        self.shorts_with_face_ai_url_file = os.path.join(base_path, "youtube_shorts_with_5_sec_with_face_ai.txt")
        self.long_with_face_ai_url_file = os.path.join(base_path, "youtube_long_with_5_sec_with_face_ai.txt")
        
        print(f"✅ Face Footage Handler initialized with base path: {base_path}")
    
    def check_face_footage_files(self):
        """
        ফেস ফুটেজের ফাইলগুলি চেক করে এবং সংখ্যা দেখায়
        
        Returns:
            dict: উভয় ফোল্ডারের ফাইল সংখ্যা
        """
        shorts_files = glob.glob(os.path.join(self.real_footage_shorts, "*.mp4")) + \
                      glob.glob(os.path.join(self.real_footage_shorts, "*.mov"))
        
        long_files = glob.glob(os.path.join(self.real_footage_long, "*.mp4")) + \
                     glob.glob(os.path.join(self.real_footage_long, "*.mov"))
        
        file_counts = {
            "shorts": len(shorts_files),
            "long": len(long_files)
        }
        
        print(f"🔍 Found {file_counts['shorts']} shorts face footage files")
        print(f"🔍 Found {file_counts['long']} long face footage files")
        
        return file_counts
    
    def get_random_face_footage(self, is_short=True, max_duration=5.0):
        """
        রিয়েল ফুটেজ ফোল্ডার থেকে র‍্যান্ডমভাবে একটি ফুটেজ বেছে নেয়
        এবং প্রয়োজনে সেটাকে ট্রিম করে নির্দিষ্ট সময়ের মধ্যে রাখে।
        
        Args:
            is_short (bool): শর্টস না লং ভিডিও
            max_duration (float): সর্বোচ্চ সময়সীমা সেকেন্ডে
        
        Returns:
            str: বেছে নেওয়া ফুটেজের পাথ (ট্রিম করা হলে টেম্পোরারি ফাইল)
        """
        # উপযুক্ত ফোল্ডার থেকে ফাইলগুলি পায়
        folder = self.real_footage_shorts if is_short else self.real_footage_long
        
        face_files = glob.glob(os.path.join(folder, "*.mp4")) + \
                     glob.glob(os.path.join(folder, "*.mov"))
        
        if not face_files:
            print(f"⚠️ No face footage files found in {folder}")
            return None
        
        # র‍্যান্ডমভাবে একটি ফাইল বেছে নেয়
        selected_file = random.choice(face_files)
        
        # ভিডিওর ডিউরেশন চেক করে
        try:
            duration = float(
                subprocess.check_output(
                    f'ffprobe -i "{selected_file}" -show_entries format=duration -v quiet -of csv="p=0"',
                    shell=True
                ).decode().strip()
            )
        except Exception as e:
            print(f"⚠️ Error checking duration of {selected_file}: {e}")
            return selected_file
        
        # যদি দৈর্ঘ্য নির্দিষ্ট সীমার মধ্যে থাকে, তবে সরাসরি ফিরিয়ে দেয়
        if duration <= max_duration:
            print(f"✅ Selected face footage: {os.path.basename(selected_file)} (Duration: {duration:.2f}s)")
            return selected_file
        
        # ডিউরেশন বেশি হলে, প্রথম max_duration সেকেন্ড কেটে নেয়
        print(f"⚠️ Selected footage is too long ({duration:.2f}s). Trimming to {max_duration:.2f}s")
        
        # টেম্পোরারি ফাইল নেম জেনারেট করে
        temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_file.close()
        trimmed_file = temp_file.name
        
        # ffmpeg দিয়ে ট্রিম করে (অডিও ছাড়া শুধু ভিডিও ট্র্যাক)
        trim_cmd = f'ffmpeg -i "{selected_file}" -t {max_duration} -c:v copy -an "{trimmed_file}" -y'
        subprocess.run(trim_cmd, shell=True)
        
        print(f"✅ Trimmed and using first {max_duration:.2f}s of {os.path.basename(selected_file)}")
        return trimmed_file
    
    def combine_face_and_stock_footage(self, face_footage, stock_footage, output_file, audio_file, audio_duration):
        """
        ফেস ফুটেজ এবং স্টক ফুটেজ কম্বাইন করে একটি ভিডিও তৈরি করে
        
        Args:
            face_footage (str): ফেস ফুটেজের পাথ
            stock_footage (str): স্টক ফুটেজের পাথ (ইতিমধ্যে লুপ করা)
            output_file (str): আউটপুট ভিডিওর পাথ
            audio_file (str): অডিও ফাইলের পাথ
            audio_duration (float): অডিওর দৈর্ঘ্য সেকেন্ডে
            
        Returns:
            bool: সফল হলে True, অন্যথায় False
        """
        try:
            # ফেস ফুটেজের দৈর্ঘ্য জানতে
            face_duration = float(
                subprocess.check_output(
                    f'ffprobe -i "{face_footage}" -show_entries format=duration -v quiet -of csv="p=0"',
                    shell=True
                ).decode().strip()
            )
            
            # স্টক ফুটেজের দৈর্ঘ্য (অডিও দৈর্ঘ্য - ফেস দৈর্ঘ্য)
            remaining_duration = max(0, audio_duration - face_duration)
            
            # অস্থায়ী ফাইলের নাম
            temp_dir = os.path.dirname(output_file)
            stock_trimmed = os.path.join(temp_dir, "stock_trimmed.mp4")
            
            # স্টক ফুটেজকে বাকি সময়ের জন্য ট্রিম করা
            if remaining_duration > 0:
                trim_cmd = f'ffmpeg -i "{stock_footage}" -t {remaining_duration} -an "{stock_trimmed}" -y'
                subprocess.run(trim_cmd, shell=True)
                
                # টেম্পোরারি ফাইলের জন্য লিস্ট তৈরি করা
                temp_list = os.path.join(temp_dir, "concat_list.txt")
                with open(temp_list, "w") as f:
                    f.write(f"file '{os.path.abspath(face_footage)}'\n")
                    f.write(f"file '{os.path.abspath(stock_trimmed)}'\n")
                
                # ফাইলগুলি কনক্যাট করা
                concat_cmd = f'ffmpeg -f concat -safe 0 -i "{temp_list}" -c copy "{output_file}" -y'
                subprocess.run(concat_cmd, shell=True)
                
                # ক্লিনআপ
                os.remove(temp_list)
                os.remove(stock_trimmed)
                
                print(f"✅ Combined footage: {face_duration:.2f}s face + {remaining_duration:.2f}s stock")
                return True
            else:
                # ফেস ফুটেজই যথেষ্ট
                shutil.copy2(face_footage, output_file)
                print(f"✅ Using only face footage: {face_duration:.2f}s (sufficient for audio)")
                return True
                
        except Exception as e:
            print(f"❌ Error combining footage: {e}")
            return False
    # Create a simpler, more reliable transition that works with FFmpeg
def create_smooth_transition(face_footage, stock_footage, output_file, transition_time=1.0):
    """
    Create a smooth transition between face footage and stock footage
    
    Args:
        face_footage (str): Path to face footage
        stock_footage (str): Path to stock footage
        output_file (str): Path to output file
        transition_time (float): Transition duration in seconds
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the duration of face footage
        face_duration = float(
            subprocess.check_output(
                f'ffprobe -i "{face_footage}" -show_entries format=duration -v quiet -of csv="p=0"',
                shell=True
            ).decode().strip()
        )
        
        # Calculate the overlap point (slightly before end of face footage)
        overlap_point = max(0, face_duration - transition_time)
        
        # Create a crossfade filter
        complex_filter = (
            f"[0:v]trim=0:{overlap_point},setpts=PTS-STARTPTS[firstpart];"
            f"[0:v]trim={overlap_point}:{face_duration},setpts=PTS-STARTPTS[fadeoutpart];"
            f"[1:v]trim=0:{transition_time},setpts=PTS-STARTPTS[fadeinpart];"
            f"[1:v]trim={transition_time},setpts=PTS-STARTPTS[secondpart];"
            f"[fadeoutpart][fadeinpart]xfade=transition=fade:duration={transition_time}:offset=0[xfaded];"
            f"[firstpart][xfaded][secondpart]concat=n=3:v=1:a=0"
        )
        
        # Execute the command
        cmd = (
            f'ffmpeg -i "{face_footage}" -i "{stock_footage}" '
            f'-filter_complex "{complex_filter}" '
            f'-c:v libx264 -pix_fmt yuv420p "{output_file}" -y'
        )
        
        subprocess.run(cmd, shell=True, check=True)
        return True
        
    except Exception as e:
        print(f"❌ Error creating transition: {e}")
        return False
    
    def get_url_files(self):
        """
        ফেস ফুটেজ URL ফাইলগুলির অস্তিত্ব এবং বিষয়বস্তু যাচাই করে
        
        Returns:
            dict: প্রতিটি ফাইলের সাথে সম্পর্কিত লিংকের তালিকা
        """
        url_data = {}
        
        # প্রতিটি URL ফাইল চেক করা
        for file_type, file_path in [
            ("shorts_with_face", self.shorts_with_face_url_file),
            ("long_with_face", self.long_with_face_url_file),
            ("shorts_with_face_ai", self.shorts_with_face_ai_url_file),
            ("long_with_face_ai", self.long_with_face_ai_url_file)
        ]:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    urls = [line.strip() for line in f.readlines() if line.strip()]
                url_data[file_type] = urls
                print(f"✅ Found {len(urls)} URLs in {os.path.basename(file_path)}")
            else:
                url_data[file_type] = []
                print(f"⚠️ URL file not found: {os.path.basename(file_path)}")
        
        return url_data
    
    def get_video_type_info(self, url_file):
        """
        URL ফাইলের নাম থেকে ভিডিওর টাইপ সম্পর্কিত তথ্য বের করে
        
        Args:
            url_file (str): URL ফাইলের পাথ
            
        Returns:
            tuple: (is_short, use_ai_voice) - শর্টস কিনা, AI ভয়েস ব্যবহার করবে কিনা
        """
        filename = os.path.basename(url_file).lower()
        is_short = "shorts" in filename
        use_ai_voice = "_ai" in filename
        
        return is_short, use_ai_voice

    def prepare_combined_video(self, temp_folder, audio_file, audio_duration, is_short):
        """
        একটি ফেস ফুটেজ এবং স্টক ফুটেজ কম্বাইন করে প্রিপেয়ার্ড ভিডিও ফাইল তৈরি করে
        
        Args:
            temp_folder (str): টেম্পোরারি ফোল্ডারের পাথ
            audio_file (str): অডিও ফাইলের পাথ
            audio_duration (float): অডিওর দৈর্ঘ্য সেকেন্ডে
            is_short (bool): শর্টস না লং ভিডিও
            
        Returns:
            str: প্রিপেয়ার্ড ভিডিও ফাইলের পাথ
        """
        # ফেস ফুটেজ থেকে র‍্যান্ডম ফাইল সিলেক্ট করা
        face_footage = self.get_random_face_footage(is_short=is_short)
        
        if not face_footage:
            print("⚠️ No face footage available, using stock footage only")
            return None
        
        # স্টক ভিডিও লুপ করা হবে
        # এই ফাংশন মেইন কোডে ব্যবহৃত হবে
        # এটি নাল রিটার্ন করে, যেন আমরা বুঝতে পারি যে ফেস ফুটেজ হবে
        return face_footage
    
    def is_face_footage_url_file(self, url_file):
        """
        চেক করে যে একটি URL ফাইল ফেস ফুটেজের জন্য কিনা
        
        Args:
            url_file (str): URL ফাইলের পাথ
            
        Returns:
            bool: ফেস ফুটেজের জন্য হলে True, অন্যথায় False
        """
        basename = os.path.basename(url_file)
        return basename in [
            "youtube_shorts_with_5_sec_with_face.txt",
            "youtube_long_with_5_sec_with_face.txt",
            "youtube_shorts_with_5_sec_with_face_ai.txt", 
            "youtube_long_with_5_sec_with_face_ai.txt"
        ]