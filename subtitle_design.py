# subtitle_design.py এ পরিবর্তন করুন
import pysubs2
import hashlib
import os

def apply_design(subs, is_short=False, filename="unknown"):
    """সাবটাইটেল ডিজাইন প্রয়োগ করে - ফাইলনাম ভিত্তিক ডিজাইন নিশ্চিত করে"""
    
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
    
    print(f"✅ Applied style #{style_index}: {selected_style['font']} with {selected_style['primary']} color")
    
    return subs