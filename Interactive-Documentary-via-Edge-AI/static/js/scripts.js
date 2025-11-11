document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('uploadForm').addEventListener('submit', handleFileUpload);
    document.getElementById('languageSelect').addEventListener('change', updateSpeakers);
    updateSpeakers();  // Initialize speakers on page load

    document.getElementById('synthesizeForm').addEventListener('submit', function(event) {
        event.preventDefault();
        synthesizeText();
    });

    startSlider();
});

let currentIndex = 0;
let sliderInterval;

function handleFileUpload(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    document.getElementById('loadingMessage').innerText = 'Uploading and extracting text...';

    fetch('/upload_pdf', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('loadingMessage').innerText = 'Error uploading file.';
            console.error('Error:', data.error);
        } else {
            document.getElementById('text').value = data.text;
            document.getElementById('loadingMessage').innerText = '';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('loadingMessage').innerText = 'Error uploading file.';
    });
}

// function updateSpeakers() {
//     var languageSelect = document.getElementById('languageSelect');
//     var selectedLanguage = languageSelect.value;
//     var speakers = JSON.parse(document.getElementById('speakersData').textContent);
//     var speakerSelect = document.getElementById('speakerSelect');
//     speakerSelect.innerHTML = '';  // Clear previous options

//     if (speakers[selectedLanguage]) {
//         speakers[selectedLanguage].forEach(function(speaker) {
//             var option = document.createElement('option');
//             option.value = speaker.voice_id;
//             option.text = speaker.name;
//             speakerSelect.appendChild(option);
//         });
//     }
// }



function updateSpeakers() {
    var languageSelect = document.getElementById('languageSelect');
    var selectedLanguage = languageSelect.value;
    var speakers = JSON.parse(document.getElementById('speakersData').textContent);
    var speakerSelect = document.getElementById('speakerSelect');
    speakerSelect.innerHTML = '';  // Clear previous options

    if (speakers[selectedLanguage]) {
        speakers[selectedLanguage].forEach(function(speaker) {
            var speakerDiv = document.createElement('div');
            speakerDiv.classList.add('speaker-option');
            speakerDiv.setAttribute('data-voice-id', speaker.voice_id);

            var speakerImg = document.createElement('img');
            speakerImg.src = `/static/images/speakers/${speaker.name}.jpg`; // Assuming image files are named by speaker IDs
            
            // speakerImg.src = `/static/images/4.png`; // Assuming image files are named by speaker IDs
            
            speakerImg.alt = speaker.name;

            speakerDiv.appendChild(speakerImg);
            speakerSelect.appendChild(speakerDiv);

            // Add event listener for click to select the speaker
            speakerDiv.addEventListener('click', function() {
                // Remove 'selected' class from all other speaker options
                document.querySelectorAll('.speaker-option').forEach(function(option) {
                    option.classList.remove('selected');
                });

                // Add 'selected' class to the clicked speaker
                speakerDiv.classList.add('selected');

                // Store the selected speaker's ID in a hidden input or directly in formData
                document.getElementById('speakerSelect').setAttribute('data-selected-speaker', speaker.voice_id);
            });
        });
    }
}

function estimateTime(text) {
    const AVERAGE_TIME_PER_SENTENCE = 2.5;
    const sentences = text.match(/[^\.!\?]+[\.!\?]+/g) || [];
    const numberOfSentences = sentences.length;
    const estimatedTime = numberOfSentences * AVERAGE_TIME_PER_SENTENCE;
    return estimatedTime;
}

function synthesizeText() {
    // var form = document.getElementById('synthesizeForm');
    // var formData = new FormData(form);
    // var jsonData = {};
    // formData.forEach((value, key) => jsonData[key] = value);

    var form = document.getElementById('synthesizeForm');
    var formData = new FormData(form);
    
    // Get selected speaker
    var selectedSpeaker = document.getElementById('speakerSelect').getAttribute('data-selected-speaker');
    if (!selectedSpeaker) {
        alert('Please select a speaker.');
        return;
    }
    formData.append('speaker', selectedSpeaker);

    var jsonData = {};
    formData.forEach((value, key) => jsonData[key] = value);




    const estimatedTime = estimateTime(jsonData.text);
    document.getElementById('estimatedTime').textContent = `Estimated time: ${estimatedTime.toFixed(2)} seconds`;

    Array.from(form.elements).forEach(element => element.disabled = true);
    var loadingMessage = document.createElement('p');
    loadingMessage.id = 'loadingMessage';
    loadingMessage.innerText = 'Loading...';
    form.appendChild(loadingMessage);

    fetch('/synthesize', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(jsonData)
    })
    .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let receivedLength = 0;
        let buffer = '';

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    loadingMessage.innerText = 'Completed!';
                    return;
                }

                receivedLength += value.length;
                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                let boundary = buffer.indexOf('\n');
                while (boundary !== -1) {
                    const jsonChunk = buffer.slice(0, boundary);
                    buffer = buffer.slice(boundary + 1);

                    try {
                        const data = JSON.parse(jsonChunk);
                        if (data.progress) {
                            loadingMessage.innerText = `Progress: ${data.progress.toFixed(2)}%`;
                        } else if (data.redirect_url) {
                            window.location.href = data.redirect_url;
                        } else if (data.error) {
                            alert('Synthesis failed: ' + data.error);
                            Array.from(form.elements).forEach(element => element.disabled = false);
                            loadingMessage.remove();
                        }
                    } catch (e) {
                        console.error('Error parsing JSON:', e);
                    }

                    boundary = buffer.indexOf('\n');
                }

                read();
            });
        }

        read();
    })
    .catch(error => {
        alert('Error: ' + error);
        Array.from(form.elements).forEach(element => element.disabled = false);
        loadingMessage.remove();
    });
}

function startSlider() {
    const slides = document.querySelectorAll('.slide');
    if (slides.length > 0) {
        slides[currentIndex].classList.add('active');
        sliderInterval = setInterval(() => {
            navigateSlider(1);
        }, 5000);
    }
}

function navigateSlider(direction) {
    const slides = document.querySelectorAll('.slide');
    const totalSlides = slides.length;
    slides[currentIndex].classList.remove('active');
    currentIndex = (currentIndex + direction + totalSlides) % totalSlides;
    slides[currentIndex].classList.add('active');
    resetSliderInterval();
}

function resetSliderInterval() {
    clearInterval(sliderInterval);
    sliderInterval = setInterval(() => {
        navigateSlider(1);
    }, 5000);
}
