import streamlit as str
import requests

# ১. অ্যাপের টাইটেল বা নাম সেট করা
str.title("🤖 আমার প্রথম এআই টুল (My AI Tool)")
str.write("এখানে কিছু লিখুন, এআই আপনাকে উত্তর দেবে।")

# ২. ব্যবহারকারীর কাছ থেকে ইনপুট নেওয়ার বক্স
user_input = str.text_input("আপনার প্রশ্ন লিখুন:", "একটি বিড়ালের গল্প বলো।")

# ৩. ফ্রি এআই মডেলের লিংক (Hugging Face API)
API_URL = "https://huggingface.co"
# নোট: এখানে আপনার একটি ফ্রি Hugging Face API Token বসাতে হবে
headers = {"Authorization": "Bearer YOUR_FREE_API_TOKEN_HERE"} 

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

# ৪. বাটন চাপলে এআই কাজ শুরু করবে
if str.button("এআই-কে জিজ্ঞেস করুন"):
    if user_input:
        str.info("এআই চিন্তা করছে...")
        output = query({"inputs": user_input})
        
        # ৫. উত্তর স্ক্রিনে দেখানো
        try:
            ai_response = output[0]['generated_text']
            str.success("এআই-এর উত্তর:")
            str.write(ai_response)
        except:
            str.error("দুঃখিত, এপিআই কানেক্ট হতে পারছে না। টোকেনটি চেক করুন।")
