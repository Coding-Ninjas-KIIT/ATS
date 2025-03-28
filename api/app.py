from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pandas as pd
import requests
import textstat
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer

# Download required NLTK resources
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')
nltk.download('omw-1.4')

# Initialize Flask app and enable CORS
app = Flask(__name__)
CORS(app)

# Preprocess text
def preprocess_text(text):
    text = text.lower()
    words = word_tokenize(text)
    words = [word for word in words if word.isalnum()]
    stop_words = set(stopwords.words('english'))
    words = [word for word in words if word not in stop_words]
    return ' '.join(words)

# Compute cosine similarity
def compute_cosine_similarity(text1, text2):
    if not text1 or not text2:
        return 0.0

    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([text1, text2])
    cosine_similarity = np.dot(vectors[0].toarray(), vectors[1].toarray().T)[0][0]
    return cosine_similarity * 10

# Extract text from JSON resume
def extract_text_from_json(resume_data):
    sections = []
    education = resume_data.get("education", {})
    sections.append(education.get("degree", ""))
    sections.append(education.get("university", ""))

    for exp in resume_data.get("experience", []):
        sections.append(exp.get("role", ""))
        sections.append(exp.get("organization", ""))
        sections.extend(exp.get("responsibilities", []))

    for proj in resume_data.get("projects", []):
        sections.append(proj.get("name", ""))
        sections.extend(proj.get("description", []))

    return " ".join(filter(None, sections))

# Extract skills from JSON resume
def extract_skills_from_json(resume_data):
    skills = []
    technical_skills = resume_data.get("technical_skills", {})
    for skill_list in technical_skills.values():
        if isinstance(skill_list, list):
            skills.extend(skill_list)

    return " ".join(skills)

# Calculate grammar score
def calculate_grammar_score(text):
    url = "https://api.languagetool.org/v2/check"
    params = {"text": text, "language": "en-US"}
    response = requests.post(url, data=params)

    if response.status_code == 200:
        matches = response.json().get("matches", [])
        num_errors = len(matches)
        total_words = len(text.split())
        return max(0.5, 1 - (num_errors / max(1, total_words)))

    return 0.8

# Calculate structure score
def calculate_structure_score(resume_data):
    score = 0
    total_weight = 5

    if resume_data.get("education"): score += 1
    if resume_data.get("experience"): score += 1
    if resume_data.get("projects"): score += 1
    if resume_data.get("technical_skills"): score += 1
    if resume_data.get("certifications"): score += 1

    return score / total_weight

# Calculate readability score
def calculate_readability_score(text):
    raw_readability = textstat.flesch_reading_ease(text)
    scaled_score = (raw_readability + 100) / 150
    return max(0.3, min(1, scaled_score))

# Calculate vocabulary score
def calculate_vocabulary_score(text):
    words = word_tokenize(text.lower())
    words = [word for word in words if word.isalnum()]
    stop_words = set(stopwords.words('english'))
    filtered_words = [word for word in words if word not in stop_words]

    unique_words = set(filtered_words)
    total_words = len(filtered_words)

    unique_ratio = len(unique_words) / max(1, total_words)
    return min(1, max(0.5, 0.5 + (0.5 * unique_ratio)))

# Calculate final ATS score
def calculate_final_score(keyword_match, section_structure, formatting_compliance, readability_score, grammar_score, structure_score, vocab_score):
    weights = {
        "keyword_match": 0.3, "section_structure": 0.1, "formatting_compliance": 0.05,
        "readability": 0.15, "grammar": 0.2, "structure": 0.1, "vocab": 0.1
    }

    final_score = (weights["keyword_match"] * keyword_match +
                   weights["section_structure"] * section_structure +
                   weights["formatting_compliance"] * formatting_compliance +
                   weights["readability"] * readability_score +
                   weights["grammar"] * grammar_score +
                   weights["structure"] * structure_score +
                   weights["vocab"] * vocab_score)

    return min(final_score, 98)

# Process resume
def process_resume(resume_data, job_description):
    text = extract_text_from_json(resume_data)
    skills = extract_skills_from_json(resume_data)

    keyword_match = compute_cosine_similarity(skills, job_description)
    readability_score = calculate_readability_score(text)
    grammar_score = calculate_grammar_score(text)
    structure_score = calculate_structure_score(resume_data)
    vocab_score = calculate_vocabulary_score(text)

    section_structure = 1 if text else 0
    formatting_compliance = 1

    final_score = calculate_final_score(keyword_match, section_structure, formatting_compliance, readability_score, grammar_score, structure_score, vocab_score)

    return {
        "Keyword Match": keyword_match,
        "Final Score": final_score
    }

@app.route('/evaluate-resume', methods=['POST'])
def evaluate_resume():
    data = request.json

    job_description = data.get('job_description')
    resume_data = data.get('resume_data')

    if not job_description or not resume_data:
        return jsonify({"error": "Both 'job_description' and 'resume_data' are required"}), 400

    result = process_resume(resume_data, job_description)

    return jsonify(result)

def handler(event, context):
    return app(event, context)

if __name__ == "__main__":
    app.run(debug=True)
