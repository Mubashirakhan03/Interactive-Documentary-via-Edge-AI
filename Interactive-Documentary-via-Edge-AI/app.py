import os
import uuid
import json
import time
import logging
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pdfplumber
import stanza
import nltk
from pydub import AudioSegment
from googletrans import Translator
import translators as ts
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for, redirect, Response, stream_with_context
from werkzeug.utils import secure_filename
from nltk.tokenize import sent_tokenize
from models import db, SynthesisRecord
import asyncio

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///synthesis.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey'
db.init_app(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RESOURCE_DIR = 'resources'
STANZA_RESOURCES_DIR = os.path.join(RESOURCE_DIR, 'stanza')
NLTK_RESOURCES_DIR = os.path.join(RESOURCE_DIR, 'nltk')
COMBINED_AUDIO_DIR = 'static/audio'

os.makedirs(STANZA_RESOURCES_DIR, exist_ok=True)
os.makedirs(NLTK_RESOURCES_DIR, exist_ok=True)
os.makedirs(COMBINED_AUDIO_DIR, exist_ok=True)

os.environ['STANZA_RESOURCES_DIR'] = STANZA_RESOURCES_DIR
nltk.data.path.append(NLTK_RESOURCES_DIR)
nltk.download('punkt', download_dir=NLTK_RESOURCES_DIR)

API_URL = 'http://localhost:8001'

MODEL_TO_LANGUAGE = {
    'v3_de.pt': 'German',
    'v3_en.pt': 'English',
    'v3_en_indic.pt': 'Indian English',
    'v3_es.pt': 'Spanish',
    'v3_fr.pt': 'French',
    'v3_indic.pt': 'Hindi',
    'v3_1_ru.pt': 'Russian',
    'v3_ua.pt': 'Ukrainian',
    'v3_tt.pt': 'Tatar',
    'v3_uz.pt': 'Uzbek'
}

LANGUAGE_TO_MODEL = {
    'de': 'v3_de.pt',
    'en': 'v3_en.pt',
    'es': 'v3_es.pt',
    'fr': 'v3_fr.pt',
    'ru': 'v3_1_ru.pt',
    'uk': 'v3_ua.pt',
    'uz': 'v3_uz.pt',
    'hi': 'v3_indic.pt',
    'tt': 'v3_tt.pt'
}

TRANSLATE_LANGUAGE_CODES = {
    'de': 'de',
    'en': 'en',
    'es': 'es',
    'fr': 'fr',
    'ru': 'ru',
    'uk': 'uk',
    'uz': 'uz',
    'hi': 'hi',
    'tt': 'tt'
}

SUPPORTED_LANGUAGES = {'de', 'en', 'es', 'fr', 'ru', 'uk'}

nlp_pipelines = {}
nlp_lock = Lock()
initialization_done = False

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

with open('./resources/speakers.json', 'r', encoding='utf-8') as f:
    speakers_dict = json.load(f)


def load_pipeline(language, model_id):
    if language in SUPPORTED_LANGUAGES:
        try:
            nlp_pipelines[model_id] = stanza.Pipeline(language, dir=STANZA_RESOURCES_DIR)
            logger.info(f"Pipeline for {language} loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading pipeline for {language}: {e}")
    else:
        logger.info(f"Language {language} not supported by Stanza. Using NLTK for sentence segmentation.")


async def load_and_log(language, model_id):
    try:
        logger.info(f"Loading pipeline for {language} with model ID {model_id}")
        await asyncio.to_thread(load_pipeline, language, model_id)
        logger.info(f"Successfully loaded pipeline for {language}")
    except Exception as e:
        logger.error(f"Error loading pipeline for {language} with model ID {model_id}: {e}")


async def initialize_pipelines():
    tasks = [load_and_log(language, model_id) for language, model_id in LANGUAGE_TO_MODEL.items()]
    await asyncio.gather(*tasks)
    logger.info(f"All pipelines: {nlp_pipelines}")
    print(nlp_pipelines, "nlp_pipelines")


def get_nlp_pipeline(selected_language, language_model_id):
    with nlp_lock:
        if language_model_id not in nlp_pipelines and selected_language in SUPPORTED_LANGUAGES:
            load_pipeline(selected_language, language_model_id)
        return nlp_pipelines.get(language_model_id)


def translate_text(text, src, dest):
    logger.info(f"Translating text from {src} to {dest}")
    translator = Translator()
    try:
        if dest in TRANSLATE_LANGUAGE_CODES.values():
            translated_text = translator.translate(text, src=src, dest=dest).text
        else:
            translated_text = ts.translate_text(text, translator='google', from_language=src, to_language=dest)
        return translated_text
    except ValueError:
        translated_text = ts.translate_text(text, translator='google', from_language=src, to_language=dest)
        return translated_text
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        return text


@app.route('/get_languages', methods=['GET'])
def get_languages():
    languages = {model_id: MODEL_TO_LANGUAGE.get(model_id, model_id) for model_id in MODEL_TO_LANGUAGE}
    return jsonify(languages)


@app.route('/get_speakers', methods=['GET'])
def get_speakers():
    return jsonify(speakers_dict)


@app.route('/synthesize', methods=['POST'])
def synthesize():
    def generate():
        try:
            data = request.json
            speaker = data['speaker']
            text = data['text']
            language_model_id = data['language']
            logger.info(f"Synthesize request received with language model ID: {language_model_id}")

            session = set_language(language_model_id)
            if not session:
                raise ValueError("Failed to create session for language model")

            selected_language = None
            for lang, model_id in LANGUAGE_TO_MODEL.items():
                if model_id == language_model_id:
                    selected_language = lang
                    break

            if not selected_language:
                yield json.dumps({"error": "Invalid language model ID"}) + '\n'
                return

            translate_language_code = TRANSLATE_LANGUAGE_CODES[selected_language]
            logger.info(f"Selected language: {selected_language}")
            start_time = time.time()

            detected_language = Translator().detect(text).lang
            if language_model_id == 'v3_en_indic.pt' and detected_language != 'en':
                text = translate_text(text, src=detected_language, dest='en')
            elif language_model_id != 'v3_indic.pt' and detected_language != translate_language_code:
                text = translate_text(text, src=detected_language, dest=translate_language_code)

            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Translation completed in {elapsed_time} seconds")

            start_time = time.time()

            if selected_language in SUPPORTED_LANGUAGES or language_model_id == 'v3_indic.pt':
                nlp = get_nlp_pipeline('en' if language_model_id == 'v3_indic.pt' else translate_language_code, language_model_id)
                if not nlp:
                    raise RuntimeError(f"Pipeline for {selected_language} could not be loaded")
                doc = nlp(text)
                text_lines = [sentence.text for sentence in doc.sentences]
            else:
                text_lines = sent_tokenize(text)

            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Sentence segmentation completed in {elapsed_time} seconds")

            audio_files = []
            sentence_times = []

            current_time = 0

            start_time = time.time()

            total_lines = len(text_lines)

            def synthesize_line(index, line):
                payload = {
                    'speaker': speaker,
                    'text': line,
                    'session': session
                }
                response = requests.post(f"{API_URL}/tts/generate", json=payload, timeout=60)
                if response.status_code == 200:
                    filename = f"{uuid.uuid4()}.wav"
                    filepath = os.path.join(COMBINED_AUDIO_DIR, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    audio = AudioSegment.from_wav(filepath)
                    duration = len(audio) / 1000
                    return index, filepath, line, duration
                else:
                    logger.error(f"Failed to generate audio for line: {line}, Response: {response.text}")
                    return index, None, None, None

            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(synthesize_line, i, line): i for i, line in enumerate(text_lines)}
                results = []
                for future in as_completed(futures):
                    results.append(future.result())
                    progress_percentage = (len(results) / total_lines) * 100
                    yield json.dumps({"progress": progress_percentage}) + '\n'

            results.sort()  # Sort results by their original index

            for index, filepath, line, duration in results:
                if filepath and line:
                    audio_files.append(filepath)
                    sentence_times.append({'text': line, 'start_time': current_time, 'end_time': current_time + duration})
                    current_time += duration + 0.5  # Adding silence duration
                else:
                    yield json.dumps({"error": "Failed to generate audio for a line"}) + '\n'
                    return

            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Speech synthesis completed in {elapsed_time} seconds")

            combined_audio_path = combine_audio_files(audio_files)

            audio_id = str(uuid.uuid4())
            new_record = SynthesisRecord(
                audio_id=audio_id,
                audio_url=f"/play_audio/{os.path.basename(combined_audio_path)}",
                sentences=json.dumps(sentence_times)
            )
            db.session.add(new_record)
            db.session.commit()

            redirect_url = url_for('show_text_audio', audio_id=audio_id)
            yield json.dumps({"redirect_url": redirect_url}) + '\n'

        except ValueError as e:
            logger.error(f"Value error: {e}")
            yield json.dumps({"error": str(e)}) + '\n'
        except RuntimeError as e:
            logger.error(f"Runtime error: {e}")
            yield json.dumps({"error": str(e)}) + '\n'
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            yield json.dumps({"error": f"An unexpected error occurred: {e}"}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')


def combine_audio_files(audio_files):
    combined = AudioSegment.silent(duration=0)
    for audio_file in audio_files:
        audio = AudioSegment.from_wav(audio_file)
        combined += audio + AudioSegment.silent(duration=500)
        os.remove(audio_file)

    combined_filename = f"combined_{uuid.uuid4()}.mp3"
    combined_filepath = os.path.join(COMBINED_AUDIO_DIR, combined_filename)
    combined.export(combined_filepath, format="mp3")
    return combined_filepath


@app.route('/play_audio/<filename>')
def play_audio(filename):
    return send_from_directory(COMBINED_AUDIO_DIR, filename)


def set_language(language_code):
    session_id = None
    response = requests.post(f"{API_URL}/tts/session", json={'language_id': language_code})
    if response.status_code == 200:
        session_id = response.json().get("session_id")
        print("Session ID:", session_id)
    else:
        print("Failed to create session:", response.json())
    return session_id


@app.route('/show_text_audio', methods=['GET'])
def show_text_audio():
    audio_id = request.args.get('audio_id')
    record = SynthesisRecord.query.filter_by(audio_id=audio_id).first()
    if record:
        return render_template('text_audio.html', sentences=json.loads(record.sentences), audio_url=record.audio_url)
    else:
        return "Record not found", 404


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        text = extract_text_from_pdf(file_path)
        return jsonify({"text": text}), 200
    return jsonify({"error": "Invalid file format"}), 400


@app.route('/')
def index():
    return render_template('index.html', languages=MODEL_TO_LANGUAGE, speakers=speakers_dict)


def extract_text_from_pdf(file_path):
    text = ''
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    return text


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        asyncio.run(initialize_pipelines())

    app.run(debug=False)



