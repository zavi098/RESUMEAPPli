import streamlit as st
import PyPDF2 as pdf
import os
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai
from pymongo import MongoClient
import re
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize MongoDB client
client = MongoClient(os.getenv("MONGODB_URI"))
db = client['your_database']  # Change to your database name
collection = db['evaluations']  # Collection for resume evaluations

# Create directory for saving resumes if it doesn't exist
resume_save_path = "uploaded_resumes"
os.makedirs(resume_save_path, exist_ok=True)

# Initialize session state
if 'shortlisted_resumes' not in st.session_state:
    st.session_state.shortlisted_resumes = []

# Function to read PDF files
def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

# Function to get AI response (simulate LLM)
def get_gemini_response(input):
    model = genai.GenerativeModel('gemini-1.0-pro')
    response = model.generate_content(input)
    return response.text

# Function to extract a brief description from the AI response
def extract_description(response):
    lines = response.split("\n")
    description = " ".join(lines[:2])  # Adjust as necessary
    return description

def extract_name_and_email(resume_text):
    # Simple regex patterns for name and email extraction
    name_pattern = r'(?i)(?<=Name: |name: |NAME: )([A-Za-z\s]+)'
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    name_match = re.search(name_pattern, resume_text)
    email_match = re.search(email_pattern, resume_text)
    
    name = name_match.group(0).strip() if name_match else "Unknown"
    email = email_match.group(0).strip() if email_match else "No Email Found"
    
    return name, email

# Function to calculate match percentage (simple keyword matching example)
def calculate_match_percentage(keywords, resume_text):
    keyword_matches = sum(1 for keyword in keywords if keyword.lower() in resume_text.lower())
    return (keyword_matches / len(keywords)) * 100 if keywords else 0

# Main application
st.title("Resume Ranking System")


jd = st.text_area("Paste the Job Description")
uploaded_files = st.file_uploader("Upload Your Resumes", type="pdf", accept_multiple_files=True,
                                  help="Please upload the resumes in PDF format")

submit = st.button("Submit")

if submit:
    if uploaded_files and jd:
        ranked_resumes = []
        keywords = re.findall(r'\w+', jd.lower())  # Simple keyword extraction
        
        for uploaded_file in uploaded_files:
            text = input_pdf_text(uploaded_file)
            if text:
                # Extract name and email from the resume
                candidate_name, candidate_email = extract_name_and_email(text)
                
                input_text = f"""
Hey Act Like a skilled or very experienced ATS (Application Tracking System) with a deep understanding of the tech field, software engineering, data science,
data analysis, and big data engineering. Your task is to evaluate the resumes based on the given job description. You must consider the job market is very competitive and you should provide the best assistance for improving the resumes. Assign the
percentage matching based on JD and the missing keywords with high accuracy.
resume:{text}
description:{jd}

I want the response as per below structure
{{"JD Match": "%", "MissingKeywords": [], "Profile Summary": ""}}
 """
                response = get_gemini_response(input_text)
                description = extract_description(response)

                match_percentage = calculate_match_percentage(keywords, text)

                resume_data = {
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email,
                    "match_percentage": match_percentage,
                    "description": description
                }

                ranked_resumes.append(resume_data)

                # Save the uploaded resume to a specific folder
                save_path = os.path.join(resume_save_path, f"{uploaded_file.name}")
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Save to MongoDB
                collection.insert_one(resume_data)  # Save to MongoDB

        ranked_resumes = sorted(ranked_resumes, key=lambda x: x["match_percentage"], reverse=True)
        df = pd.DataFrame(ranked_resumes)
        df["Rank"] = range(1, len(df) + 1)

        st.table(df[["candidate_name", "candidate_email", "Rank", "match_percentage"]].rename(columns={
            "candidate_name": "CANDIDATE_NAME",
            "candidate_email": "CANDIDATE_EMAIL",
            "match_percentage": "MATCH_PERCENTAGE",
        }))
