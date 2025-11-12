<h2><b>Project</b></h2>
A lightweight, edge-optimized NLP system that converts documentary content into interactive, real-time, speech-enabled conversations.
Supports multi-language translation, text processing, and low-latency speech synthesis for resource-constrained devices.<br><br>



## Features

-Transform static documentary text into interactive conversation

-Real-time text-to-speech synthesis

-Edge-optimized backend (low latency, lightweight)

-Multi-language support (via Stanza + translators)

-Concurrent processing for fast TTS generation

-Clean Flask API for integration with frontend or mobile apps



<h2><b>Tech Stack</b></h2>

**Backend**: Flask (Python)
**NLP**: Stanza, NLTK

**Translation**: googletrans / translators

**TTS**: External local TTS API (port 8001)

**Concurrency**: ThreadPoolExecutor, asyncio

**Storage**: SQLite

**PDF Parsing**: pdfplumber


<h2><b>How It Works</b></h2>

1. User uploads a documentary (PDF/TXT).

2. System extracts clean text using pdfplumber.

3. Stanza NLP pipeline segments text into logical conversation chunks.

4. Text is translated (optional) for TTS compatibility.

5. TTS generation happens in parallel threads for speed.

6. System streams audio output back to the user.


## Project Demo Folder

You can watch the demo of the project here:  
👉 [Click to open Demo Folder](https://github.com/Mubashirakhan03/Interactive-Documentary-via-Edge-AI/tree/main/Interactive-Documentary-via-Edge-AI/demo)



<h2><b>Run Locally</b></h2>

<pre>
#install dependencies <br>
pip install -r requirements.txt 
</pre>


<pre>
#Start Flask server <br>
python app.py 
</pre>



Make sure your <b>TTS Server</b> is running on:
<pre>
http://localhost:8001
</pre>


<h2><b>Future Improvements</b></h2>

- Stronger backend performance optimization

- Advanced encryption for secure file handling

- On-device TTS integration for complete offline edge use



## Contact
For any queries: [mubashirakhan1001@gmail.com](mailto:mubashirakhan1001@gmail.com)
