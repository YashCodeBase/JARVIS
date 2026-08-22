const STORAGE_KEY = 'jarvis_trigger_gesture';

const ENABLED_KEY = 'jarvis_gesture_enabled';
const gestureToggle = document.getElementById('gestureToggle');

function getGestureEnabled() {
  return localStorage.getItem(ENABLED_KEY) === 'true';
}

function setGestureEnabled(enabled) {
  localStorage.setItem(ENABLED_KEY, enabled ? 'true' : 'false');
}

function renderToggle(enabled) {
  gestureToggle.dataset.enabled = enabled;
  gestureToggle.textContent = enabled ? 'ON' : 'OFF';
}

gestureToggle.addEventListener('click', () => {
  const newState = !getGestureEnabled();
  setGestureEnabled(newState);
  renderToggle(newState);
});

renderToggle(getGestureEnabled());

const DEFAULT_GESTURE = 'PEACE';

const optionButtons = document.querySelectorAll('.gestureOption');

function getSavedGesture() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_GESTURE;
}

function setSavedGesture(gesture) {
  localStorage.setItem(STORAGE_KEY, gesture);
}

function highlightActive(gesture) {
  optionButtons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.gesture === gesture);
  });
}

optionButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const gesture = btn.dataset.gesture;
    setSavedGesture(gesture);
    highlightActive(gesture);
  });
});

highlightActive(getSavedGesture());
