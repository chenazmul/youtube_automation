# subtitle_design.py এ পরিবর্তন করুন
import pysubs2
import hashlib
import os
import random  # এটা যোগ করুন
import time
import whisper
import torch
import pysubs2
import random
import os

def generate_subtitles_karaoke_chunked(audio_file, subtitle_file, model, words_per_line=5):
    """
    Whisper থেকে word-level timestamps নিয়ে, প্রতি words_per_line ওয়ার্ডে চাঙ্ক করে
    ক্যারাওকে এফেক্ট সহ .ass ফাইল তৈরি করে।
    """
   
    # অডিও ফাইল লোড করা
    audio_tensor = whisper.load_audio(audio_file)
    audio_tensor = torch.from_numpy(audio_tensor).float().to(device)
    
    result = model.transcribe(audio_tensor, word_timestamps=True, task='transcribe')
    if not result or "segments" not in result or not result["segments"]:
        print(f"❌ Transcription failed or empty segments for: {audio_file}")
        with open(subtitle_file, "w", encoding="utf-8") as f:
            f.write("")
        return
    
    chunks = split_into_chunks_karaoke(result, words_per_line=words_per_line)
    subs = pysubs2.SSAFile()
    
    # ফেড ইফেক্ট র‍্যান্ডমাইজ করুন - ফেড ইন / ফেড আউট সময় পরিবর্তন করুন
    fade_in_time = random.choice([200, 300, 400, 500])
    fade_out_time = random.choice([200, 300, 400, 500])
    fade_tag = r"{\fad(" + str(fade_in_time) + "," + str(fade_out_time) + ")}"
    
    # র‍্যান্ডম কালার স্কিম নির্বাচন
    color_schemes = [
        {"primary": pysubs2.Color(255, 255, 255, 0), "secondary": pysubs2.Color(0, 255, 0, 0)},  # সাদা/সবুজ
        {"primary": pysubs2.Color(255, 255, 255, 0), "secondary": pysubs2.Color(255, 255, 0, 0)},  # সাদা/হলুদ
        {"primary": pysubs2.Color(255, 255, 255, 0), "secondary": pysubs2.Color(0, 191, 255, 0)},  # সাদা/নীল
        {"primary": pysubs2.Color(255, 255, 255, 0), "secondary": pysubs2.Color(255, 0, 0, 0)},  # সাদা/লাল
        {"primary": pysubs2.Color(0, 0, 0, 0), "secondary": pysubs2.Color(0, 255, 0, 0)},  # কালো/সবুজ
    ]
    selected_scheme = random.choice(color_schemes)
    
    # র‍্যান্ডম ফন্ট নির্বাচন
    fonts = ["Montserrat", "Arial", "Roboto", "Futura", "Impact", "Helvetica"]
    selected_font = random.choice(fonts)
    
    # র‍্যান্ডম স্টাইল প্যারামিটার নির্বাচন
    font_size = random.randint(22, 28)
    outline_size = random.randint(2, 4)
    shadow_size = random.randint(1, 3)
    margin_v = random.randint(40, 70)
    
    # র‍্যান্ডম পজিশন নির্বাচন
    positions = {
        "top": 8,
        "bottom": 2,
        "middle": 5,
        "top-left": 7,
        "top-right": 9,
        "bottom-left": 1,
        "bottom-right": 3,
        "right": 6,
        "left": 4,
    }
    # selected_position = random.choice(list(positions.keys()))
    # alignment = positions[selected_position]
    
    # এর পরিবর্তে এটি লিখুন:
    selected_position = "right"
    alignment = positions[selected_position]  # এটি 6 হবে
    
    # ফাইলনাম থেকে সিড নির্ধারণ করুন (সাবটাইটেল কনসিস্টেন্সি নিশ্চিত করতে)
    base_filename = os.path.basename(audio_file)
    # ফাইলনাম থেকে একটি সংখ্যা তৈরি করুন
    filename_seed = sum(ord(c) for c in base_filename)
    random.seed(filename_seed)  # র‍্যান্ডম সিড সেট করুন
    
    for chunk in chunks:
        start_ms = chunk["start"] * 1000
        end_ms = chunk["end"] * 1000
        karaoke_line = chunk["text"]
        
        # কালার ইফেক্ট প্রয়োগ করুন - কিছু রঙই বদলান
        if random.choice([True, False]):  # 50% সম্ভাবনা
            color_tag = r"{\c&H" + format(random.randint(0, 255), '02X') + format(random.randint(0, 255), '02X') + format(random.randint(0, 255), '02X') + "&}"
            karaoke_line = color_tag + karaoke_line
        
        karaoke_line = fade_tag + karaoke_line
        karaoke_line = karaoke_line.upper() if random.choice([True, False]) else karaoke_line
        
        event = pysubs2.SSAEvent(
            start=start_ms,
            end=end_ms,
            text=karaoke_line
        )
        subs.append(event)
    
    # স্টাইল সেট করুন
    subs.styles["Default"].fontname = selected_font
    subs.styles["Default"].fontsize = font_size
    subs.styles["Default"].bold = random.choice([True, False])
    subs.styles["Default"].italic = random.choice([True, False])
    subs.styles["Default"].underline = random.choice([True, False])
    subs.styles["Default"].alignment = alignment
    subs.styles["Default"].outline = outline_size
    subs.styles["Default"].shadow = shadow_size
    subs.styles["Default"].borderstyle = random.choice([1, 3])  # 1=আউটলাইন+শ্যাডো, 3=অপাক বক্স
    subs.styles["Default"].marginv = margin_v
    
    # প্রাইমারি এবং সেকেন্ডারি কালার সেট করুন
    subs.styles["Default"].primarycolor = selected_scheme["primary"]
    subs.styles["Default"].secondarycolor = selected_scheme["secondary"]
    
    # বেকগ্রাউন্ড কালার র‍্যান্ডমাইজ করুন
    bg_opacity = random.randint(0, 200)  # 0=স্বচ্ছ, 255=অস্বচ্ছ
    subs.styles["Default"].backcolor = pysubs2.Color(0, 0, 0, bg_opacity)
    
    # র‍্যান্ডম সিড রিসেট করুন
    random.seed()  # র‍্যান্ডম সিড রিসেট করে অন্যান্য প্রসেসে প্রভাব প্রতিরোধ করুন
    
    subs.save(subtitle_file)
# এই লাইনটি মুছে ফেলুন বা এভাবে পরিবর্তন করুন
    print(f"✅ Karaoke subtitles (chunked) generated with dynamic style: {subtitle_file}")
    print(f"   Style: Font={selected_font}, Position={selected_position}") 


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

def apply_design(subs, is_short=False, filename="unknown", position='bottom', 
                 vertical_margin=50, horizontal_margin=0):
    """সাবটাইটেল ডিজাইন প্রয়োগ করে - ফাইলনাম ভিত্তিক ডিজাইন নিশ্চিত করে"""
    """
    design_index = None হলে র‍্যান্ডম সিলেক্ট হবে
    """
    # যদি design_index না দেওয়া হয়, তাহলে র‍্যান্ডম সিলেক্ট করুন
    if design_index is None:
        design_index = random.randint(0, 9)
    
     # সম্পূর্ণ র‍্যান্ডম সিলেকশন
    style_index = random.randint(0, len(styles) - 1)
    
    # প্রতিবার আলাদা স্টাইল পাওয়ার জন্য টাইম-বেইজড র‍্যান্ডমাইজেশন
    random.seed(time.time())
    
    # ফাইলনাম থেকে স্টাইল ইনডেক্স নির্ধারণ করুন
    # এতে করে একই ফাইলে সবসময় একই ডিজাইন, কিন্তু ভিন্ন ফাইলে ভিন্ন ডিজাইন
    hasher = hashlib.md5(filename.encode())
    style_index = int(hasher.hexdigest(), 16) % 10  # 0-9 এর মধ্যে একটি ইনডেক্স
    
    print(f"🔹 Using style index {style_index} for file: {filename}")
    
    # 10টি সম্পূর্ণ ভিন্ন ডিজাইন (আপনার আগের কোড অনুসারে)
    styles = [
        # স্টাইল 0: সাদা টেক্সট, নিওন গ্রিন আউটলাইন
        {
            "font": "Arial", 
            "size": 25 if is_short else 32,
            "primary": (255, 255, 255),  # সাদা
            "outline": (0, 255, 0),      # নিওন গ্রিন
            "shadow": (0, 100, 0, 180),  # ডার্ক গ্রিন শ্যাডো
            "back": (0, 0, 0, 160),      # ব্ল্যাক ব্যাকগ্রাউন্ড
            "border_style": 1,           # আউটলাইন + শ্যাডো
        },
        
        # স্টাইল 1: সাদা টেক্সট, নিওন পিঙ্ক আউটলাইন
        {
            "font": "Verdana", 
            "size": 24 if is_short else 30,
            "primary": (255, 255, 255),  # সাদা 
            "outline": (255, 0, 128),    # নিওন পিঙ্ক
            "shadow": (100, 0, 50, 160), # পিঙ্ক শ্যাডো
            "back": (0, 0, 0, 150),      # ব্ল্যাক ব্যাকগ্রাউন্ড
            "border_style": 3,           # বক্স বর্ডার
        },
        
        # স্টাইল 2: গোল্ডেন টেক্সট, ডার্ক ব্লু আউটলাইন
        {
            "font": "Impact", 
            "size": 28 if is_short else 34,
            "primary": (255, 215, 0),    # গোল্ড
            "outline": (0, 0, 128),      # ডার্ক ব্লু
            "shadow": (0, 0, 60, 180),   # ব্লু শ্যাডো
            "back": (0, 0, 20, 170),     # ডার্ক ব্লু ব্যাকগ্রাউন্ড
            "border_style": 1,           # আউটলাইন + শ্যাডো
        },
        
        # স্টাইল 3: নিওন ব্লু টেক্সট, পারপল আউটলাইন
        {
            "font": "Tahoma", 
            "size": 26 if is_short else 32,
            "primary": (0, 255, 255),    # সাইনি
            "outline": (128, 0, 128),    # পারপল
            "shadow": (60, 0, 60, 160),  # পারপল শ্যাডো
            "back": (10, 0, 20, 150),    # ডার্ক পারপল ব্যাকগ্রাউন্ড
            "border_style": 3,           # বক্স বর্ডার
        },
        
        # স্টাইল 4: নিওন রেড টেক্সট, ডার্ক শ্যাডো
        {
            "font": "Arial Black", 
            "size": 24 if is_short else 30,
            "primary": (255, 0, 0),      # রেড
            "outline": (0, 0, 0),        # ব্ল্যাক
            "shadow": (30, 0, 0, 180),   # ডার্ক রেড শ্যাডো
            "back": (10, 0, 0, 160),     # ব্ল্যাকিশ রেড ব্যাকগ্রাউন্ড
            "border_style": 1,           # আউটলাইন + শ্যাডো
        },
        
        # স্টাইল 5: ইয়েলো টেক্সট, ব্ল্যাক আউটলাইন
        {
            "font": "Segoe UI", 
            "size": 26 if is_short else 32,
            "primary": (255, 255, 0),    # ইয়েলো
            "outline": (0, 0, 0),        # ব্ল্যাক
            "shadow": (40, 40, 0, 160),  # ডার্ক ইয়েলো শ্যাডো
            "back": (20, 20, 0, 140),    # ডার্ক ইয়েলোইশ ব্ল্যাক
            "border_style": 3,           # বক্স বর্ডার
        },
        
        # স্টাইল 6: পিওর হোয়াইট টেক্সট, ব্ল্যাক আউটলাইন
        {
            "font": "Franklin Gothic Medium", 
            "size": 27 if is_short else 33,
            "primary": (255, 255, 255),  # পিওর হোয়াইট
            "outline": (0, 0, 0),        # ব্ল্যাক
            "shadow": (50, 50, 50, 180), # গ্রে শ্যাডো
            "back": (0, 0, 0, 150),      # ব্ল্যাক ব্যাকগ্রাউন্ড
            "border_style": 1,           # আউটলাইন + শ্যাডো
        },
        
        # স্টাইল 7: অরেঞ্জ টেক্সট, ডার্ক রেড আউটলাইন
        {
            "font": "Candara", 
            "size": 25 if is_short else 31,
            "primary": (255, 165, 0),    # অরেঞ্জ
            "outline": (139, 0, 0),      # ডার্ক রেড
            "shadow": (60, 30, 0, 160),  # ব্রাউনিশ শ্যাডো
            "back": (20, 10, 0, 150),    # ব্ল্যাকিশ ব্রাউন
            "border_style": 3,           # বক্স বর্ডার
        },
        
        # স্টাইল 8: লাইম গ্রিন টেক্সট, ডার্ক গ্রিন আউটলাইন
        {
            "font": "Calibri", 
            "size": 24 if is_short else 32,
            "primary": (50, 205, 50),    # লাইম গ্রিন
            "outline": (0, 100, 0),      # ডার্ক গ্রিন
            "shadow": (0, 50, 0, 160),   # গ্রিন শ্যাডো
            "back": (0, 20, 0, 140),     # ডার্ক গ্রিন ব্যাকগ্রাউন্ড
            "border_style": 1,           # আউটলাইন + শ্যাডো
        },
        
        # স্টাইল 9: বাইগন অরেঞ্জ কম্বো
        {
            "font": "Corbel", 
            "size": 24 if is_short else 30,
            "primary": (255, 99, 71),    # টমাটো
            "outline": (106, 90, 205),   # স্লেটব্লু
            "shadow": (60, 50, 80, 160), # পারপ্লিশ ব্লু শ্যাডো
            "back": (30, 20, 40, 150),   # ডার্ক পারপল
            "border_style": 3,           # বক্স বর্ডার
        },
    ]
    
    # নির্বাচিত স্টাইল পান
    selected_style = styles[style_index]
    
    # ডিজাইন প্রয়োগ করুন
    subs.styles["Default"].fontname = selected_style["font"]
    subs.styles["Default"].fontsize = selected_style["size"]
    
    # কালার অ্যাপ্লাই করুন
    subs.styles["Default"].primarycolor = pysubs2.Color(*selected_style["primary"], 0)  # BGRA format
    subs.styles["Default"].outlinecolor = pysubs2.Color(*selected_style["outline"], 0)
    subs.styles["Default"].backcolor = pysubs2.Color(*selected_style["back"])
    subs.styles["Default"].shadowcolor = pysubs2.Color(0, 0, 0, 255)  # ডিফল্ট শ্যাডো
    
    # বর্ডার স্টাইল ও অন্যান্য প্যারামিটার
    subs.styles["Default"].borderstyle = selected_style["border_style"]
    subs.styles["Default"].outline = 2.5 if is_short else 3.0  # আউটলাইন ছোট/বড় করুন
    subs.styles["Default"].shadow = 1.5  # শ্যাডো ডিস্ট্যান্স
    subs.styles["Default"].alignment = 2  # সেন্টার অ্যালাইনমেন্ট
    subs.styles["Default"].marginv = 50 if is_short else 70  # মার্জিন এডজাস্ট করুন
    
    # বোল্ড এবং ইটালিক র‍্যান্ডমাইজ করুন
    subs.styles["Default"].bold = (style_index % 2 == 0)  # জোড় ইনডেক্সে বোল্ড
    subs.styles["Default"].italic = False  # ইটালিক বন্ধ রাখুন
    
     # মার্জিন সেট করুন
    if position == 'top':
        subs.styles["Default"].marginv = vertical_margin
    elif position == 'bottom':
        subs.styles["Default"].marginv = vertical_margin
    elif position == 'left':
        subs.styles["Default"].marginh = horizontal_margin
    elif position == 'right':
        subs.styles["Default"].marginh = horizontal_margin
        
    print(f"✅ Applied style #{style_index}: {selected_style['font']} with {selected_style['primary']} color")
    
    return subs

# Option 1: Define device in the file
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")