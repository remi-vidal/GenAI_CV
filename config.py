from pymongo import MongoClient
import google.generativeai as genai

# Staging

import os
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["staging"]
collection = db["data_test"]

# Production

# import streamlit as st
# api_key = st.secrets["GOOGLE_API_KEY"]
# genai.configure(api_key=api_key)
# MONGO_URI = st.secrets["MONGO_URI"]
# client = MongoClient(MONGO_URI)
# db = client["ats_database"]
# collection = db["candidatures"]