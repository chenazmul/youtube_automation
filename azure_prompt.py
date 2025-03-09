# azure_prompt.py

import os
import requests
import json

# Azure OpenAI API কনফিগারেশন
endpoint = os.getenv("ENDPOINT_URL", "https://et1.openai.azure.com/")  
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o")  

def generate_output_from_azure(transcribe, video_title, output_file_path):
    """Azure OpenAI API দিয়ে স্পিচ টেক্সট প্রসেস করা এবং আউটপুট সেভ করা"""
    
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
