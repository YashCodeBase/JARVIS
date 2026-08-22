// ===== Gesture Detection (Phase A: basic hand presence detection) =====
import { HandLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";

let handLandmarker = null;
const gestureVideo = document.getElementById('gestureVideo');

async function initGestureDetection() {
  try {
    const vision = await FilesetResolver.forVisionTasks(
      "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
    );
    handLandmarker = await HandLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
      },
      runningMode: "VIDEO",
      numHands: 1
    });

    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    gestureVideo.srcObject = stream;

    gestureVideo.addEventListener('loadeddata', () => {
      console.log('[Gesture] Camera ready, starting detection loop');
      detectLoop();
    });
  } catch (err) {
    console.error('[Gesture] Failed to initialize:', err);
  }
}

const gestureDebug = document.getElementById('gestureDebug');

// Distance between two landmark points
function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// Checks if a finger is "extended" by comparing tip distance vs pip-joint distance from the wrist
function isExtended(landmarks, tipIdx, pipIdx, wristIdx = 0) {
  return dist(landmarks[tipIdx], landmarks[wristIdx]) > dist(landmarks[pipIdx], landmarks[wristIdx]);
}

// Thumb needs a different check -- it moves sideways, not up/down like the other fingers
function isThumbExtended(landmarks) {
  const thumbTip = landmarks[4];
  const thumbMcp = landmarks[2];
  const pinkyMcp = landmarks[17];
  return dist(thumbTip, pinkyMcp) > dist(thumbMcp, pinkyMcp);
}

function classifyGesture(landmarks) {
  const thumb = isThumbExtended(landmarks);
  const index = isExtended(landmarks, 8, 6);
  const middle = isExtended(landmarks, 12, 10);
  const ring = isExtended(landmarks, 16, 14);
  const pinky = isExtended(landmarks, 20, 18);

  if (index && middle && !ring && !pinky) return 'PEACE';
  if (thumb && !index && !middle && !ring && !pinky) return 'THUMBS_UP';
  if (thumb && !index && !middle && !ring && pinky) return 'SHAKA';
  if (!thumb && !index && !middle && !ring && !pinky) return 'FIST';
  return 'NONE';
}

let currentGesture = 'NONE';

function detectLoop() {
  if (!handLandmarker) return;
  const nowMs = performance.now();
  const result = handLandmarker.detectForVideo(gestureVideo, nowMs);

  if (result.landmarks && result.landmarks.length > 0) {
    currentGesture = classifyGesture(result.landmarks[0]);
  } else {
    currentGesture = 'NONE';
  }

  gestureDebug.textContent = 'GESTURE: ' + currentGesture;
  handleGestureForMic(currentGesture);

  requestAnimationFrame(detectLoop);
}

if (localStorage.getItem('jarvis_gesture_enabled') === 'true') {
  initGestureDetection();
} else {
  console.log('[Gesture] Feature is OFF (enable it in Settings)');
  gestureDebug.textContent = 'GESTURE: OFF';
}
// ===== End Gesture Detection =====







const chat = document.getElementById('chat');
const input = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const muteBtn = document.getElementById('muteBtn');
const registerBtn = document.getElementById('registerBtn');
const statusText = document.getElementById('statusText');
const orbWrap = document.getElementById('orbWrap');
const waveform = document.getElementById('waveform');
const modeToggle = document.getElementById('modeToggle');

let voiceMuted = false;
let chatMode = 'auto';

modeToggle.addEventListener('click', (e) => {
  const btn = e.target.closest('.modeBtn');
  if (!btn) return;
  chatMode = btn.dataset.mode;
  document.querySelectorAll('.modeBtn').forEach(b => b.classList.toggle('active', b === btn));
});

function setStatus(state) {
  statusText.textContent = state;
  orbWrap.dataset.state = state;
  waveform.classList.toggle('active', state === 'SPEAKING');
}

function addMessage(text, who) {
  const div = document.createElement('div');
  div.className = 'msg ' + who;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function speak(text) {
  if (voiceMuted || !('speechSynthesis' in window)) { setStatus('READY'); return; }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.onstart = () => setStatus('SPEAKING');
  utterance.onend = () => setStatus('READY');
  utterance.onerror = () => setStatus('READY');
  window.speechSynthesis.speak(utterance);
}

async function sendMessage(text) {
  const messageText = (text !== undefined ? text : input.value).trim();
  if (!messageText) return;
  addMessage(messageText, 'user');
  input.value = '';
  sendBtn.disabled = true;
  setStatus('THINKING');
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: messageText, mode: chatMode })
    });
    const data = await res.json();
    const replyText = data.reply || '(no response)';
    addMessage(replyText, 'jarvis');
    speak(replyText);
  } catch (err) {
    addMessage('Error reaching Jarvis: ' + err, 'jarvis');
    setStatus('READY');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener('click', () => sendMessage());
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMessage(); });

muteBtn.addEventListener('click', () => {
  voiceMuted = !voiceMuted;
  muteBtn.textContent = voiceMuted ? '🔇' : '🔊';
  muteBtn.classList.toggle('active', !voiceMuted);
  if (voiceMuted) window.speechSynthesis.cancel();
});
muteBtn.classList.add('active');

registerBtn.addEventListener('click', async () => {
  try {
    registerBtn.disabled = true;
    registerBtn.textContent = 'Follow phone prompt...';
    const optionsRes = await fetch('/webauthn/register/begin');
    const optionsJSON = await optionsRes.json();
    const attResp = await SimpleWebAuthnBrowser.startRegistration(optionsJSON);
    const verifyRes = await fetch('/webauthn/register/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(attResp)
    });
    const verifyData = await verifyRes.json();
    if (verifyData.verified) {
      registerBtn.textContent = 'Registered ✓';
    } else {
      registerBtn.textContent = 'Register Device';
      alert('Registration failed: ' + (verifyData.error || 'unknown error'));
    }
  } catch (err) {
    registerBtn.textContent = 'Register Device';
    alert('Registration error: ' + err);
  } finally {
    registerBtn.disabled = false;
  }
});

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let manualMicActive = false;
let gestureMicActive = false;
let gestureRecognitionInstance = null;

function getTriggerGesture() {
  return localStorage.getItem('jarvis_trigger_gesture') || 'PEACE';
}

function handleGestureForMic(gesture) {
  if (!SpeechRecognitionAPI) return;
  const trigger = getTriggerGesture();
  const gestureMatches = gesture === trigger;

  if (gestureMatches && !gestureMicActive && !manualMicActive) {
    startGestureListening();
  } else if (!gestureMatches && gestureMicActive) {
    stopGestureListening();
  }
}

function startGestureListening() {
  gestureMicActive = true;
  gestureRecognitionInstance = new SpeechRecognitionAPI();
  gestureRecognitionInstance.continuous = true;
  gestureRecognitionInstance.interimResults = false;
  gestureRecognitionInstance.lang = 'en-US';

  gestureRecognitionInstance.onstart = () => {
    micBtn.classList.add('listening');
    setStatus('LISTENING');
  };
  gestureRecognitionInstance.onresult = (event) => {
    const lastResult = event.results[event.results.length - 1];
    sendMessage(lastResult[0].transcript);
  };
  gestureRecognitionInstance.onerror = (event) => {
    console.error('[Gesture Mic] error:', event.error);
  };
  gestureRecognitionInstance.onend = () => {
    if (gestureMicActive && currentGesture === getTriggerGesture()) {
      // Browser auto-stopped the session but you're still holding the gesture -- restart it
      gestureRecognitionInstance.start();
    } else {
      gestureMicActive = false;
      micBtn.classList.remove('listening');
      if (statusText.textContent === 'LISTENING') setStatus('READY');
    }
  };

  window.speechSynthesis.cancel();
  gestureRecognitionInstance.start();
}

function stopGestureListening() {
  gestureMicActive = false;
  if (gestureRecognitionInstance) {
    gestureRecognitionInstance.stop();
  }
}

if (SpeechRecognitionAPI) {
  const recognition = new SpeechRecognitionAPI();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';
  let isListening = false;
  recognition.onstart = () => { isListening = true; manualMicActive = true; micBtn.classList.add('listening'); setStatus('LISTENING'); };
  recognition.onresult = (event) => { sendMessage(event.results[0][0].transcript); };
  recognition.onerror = (event) => { console.error('Speech recognition error:', event.error); setStatus('READY'); };
  recognition.onend = () => { isListening = false; manualMicActive = false; micBtn.classList.remove('listening'); if (statusText.textContent === 'LISTENING') setStatus('READY'); };
  micBtn.addEventListener('click', () => {
    if (gestureMicActive) return;
    if (isListening) { recognition.stop(); }
    else { window.speechSynthesis.cancel(); recognition.start(); }
  });
} else {
  micBtn.disabled = true;
  micBtn.title = 'Speech recognition not supported in this browser (use Chrome)';
}
