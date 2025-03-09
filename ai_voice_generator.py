import os
import re
import math
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment

def sanitize_text_for_ssml(text):
    """SSML এর জন্য টেক্সট সেনিটাইজ করে"""
    # সাধারণ HTML ক্যারেক্টার এস্কেপ
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    
    # অন্যান্য সম্ভাব্য সমস্যাযুক্ত ক্যারেক্টার পরিষ্কার
    text = re.sub(r'[\u0000-\u001F\u007F-\u009F]', '', text)
    
    return text

def transcribe_and_generate_ai_voice(transcript_text, title, temp_folder, chunk_size=4000):
    """
    ট্রান্সক্রিপ্ট থেকে AI ভয়েস তৈরি করে। বড় টেক্সটগুলো ছোট ছোট চাঙ্কে ভাগ করে প্রসেস করে।
    
    Parameters:
    - transcript_text: Whisper থেকে পাওয়া ট্রান্সক্রিপ্ট
    - title: আউটপুট ফাইলের জন্য শিরোনাম
    - temp_folder: টেম্পোরারি ফাইল সংরক্ষণের জন্য ফোল্ডার
    - chunk_size: প্রতি চাঙ্কে সর্বাধিক অক্ষর সংখ্যা (Microsoft-এর TTS এর জন্য 10,000 সর্বাধিক)
    
    Returns:
    - output_audio_path: সম্পূর্ণ AI ভয়েস মিশ্রিত অডিও ফাইলের পাথ
    """
    print(f"🎙️ Generating AI voice for: {title}")
    
    # Azure স্পিচ সার্ভিস কনফিগারেশন
    speech_key = "CQT0xwEFxCRUFFpfqFNp72Fji4jyJAwNUljqTqtirXXSD4bsvVDCJQQJ99BAACYeBjFXJ3w3AAAYACOGS55e"
    service_region = "eastus"

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config.speech_synthesis_voice_name = "en-US-ChristopherNeural"  # পুরুষ কণ্ঠ
    # অন্যান্য ভাল কণ্ঠের উদাহরণ:
    # - "en-US-JasonNeural" (পুরুষ, পরিষ্কার, প্রফেশনাল)
    # - "en-US-GuyNeural" (পুরুষ, উষ্ণ, প্রাকৃতিক)
    # - "en-US-SaraNeural" (মহিলা, পরিষ্কার, প্রফেশনাল)
    # - "en-US-JennyNeural" (মহিলা, উষ্ণ, প্রাকৃতিক)
    
    speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)
    
    # চাঙ্ক ফোল্ডার তৈরি
    chunk_folder = os.path.join(temp_folder, f"{title}_ai_voice_chunks")
    os.makedirs(chunk_folder, exist_ok=True)
    
    # টেক্সট চাঙ্ক তৈরি করুন
    text = sanitize_text_for_ssml(transcript_text)
    
    # সেন্টেন্স দ্বারা ভাগ করুন যাতে মানসম্মত ব্রেক পয়েন্টে চাঙ্ক করা যায়
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    print(f"🔹 Text split into {len(chunks)} chunks for processing")
    
    # প্রতিটি চাঙ্ক প্রসেস করে AI ভয়েস তৈরি করুন
    chunk_audio_files = []
    
    for i, chunk_text in enumerate(chunks):
        chunk_filename = os.path.join(chunk_folder, f"chunk_{i}.mp3")
        
        # SSML তৈরি
        ssml_string = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' 
               xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='en-US'>
            <voice name='{speech_config.speech_synthesis_voice_name}'>
                <mstts:express-as style='excited'>
                    {chunk_text}
                </mstts:express-as>
            </voice>
        </speak>
        """
        
        # অডিও কনফিগ
        audio_config = speechsdk.audio.AudioOutputConfig(filename=chunk_filename)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        # সিনথেসাইজ
        try:
            print(f"🔹 Synthesizing chunk {i+1}/{len(chunks)}...")
            result = synthesizer.speak_ssml_async(ssml_string).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ Chunk {i+1} synthesized successfully: {chunk_filename}")
                chunk_audio_files.append(chunk_filename)
            else:
                print(f"❌ Error synthesizing chunk {i+1}: {result.reason}")
                # যদি একটি চাঙ্ক ব্যর্থ হয়, অন্যগুলো নিয়ে তবুও চালিয়ে যান
        except Exception as e:
            print(f"❌ Exception in AI Voice Generation for chunk {i+1}: {e}")
    
    if not chunk_audio_files:
        print("❌ No audio chunks were successfully synthesized")
        return None
    
    # সব অডিও চাঙ্ক একত্রিত করুন
    output_filename = os.path.join(temp_folder, f"{title}_ai_voice.mp3")
    combined = AudioSegment.empty()
    
    for audio_file in chunk_audio_files:
        try:
            segment = AudioSegment.from_file(audio_file)
            combined += segment
            
            # চাঙ্ক ফাইল ডিলিট করুন (ঐচ্ছিক)
            os.remove(audio_file)
        except Exception as e:
            print(f"❌ Error processing audio file {audio_file}: {e}")
    
    # একত্রিত অডিও সেভ করুন
    combined.export(output_filename, format="mp3")
    print(f"✅ Combined AI voice saved to: {output_filename}")
    
    # চাঙ্ক ফোল্ডার ডিলিট করুন
    try:
        os.rmdir(chunk_folder)
    except:
        print(f"⚠️ Could not delete chunk folder: {chunk_folder}")
    
    return output_filename