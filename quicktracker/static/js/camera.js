(() => {
  const video = document.getElementById('camera-video');
  if (!video) return;

  const placeholder = document.getElementById('camera-placeholder');
  const startButton = document.getElementById('start-camera');
  const captureButton = document.getElementById('capture-photo');
  const markButton = document.getElementById('mark-attendance');
  const canvas = document.getElementById('capture-canvas');
  const imagesInput = document.getElementById('images-input');
  const captureCount = document.getElementById('capture-count');
  const thumbs = document.getElementById('capture-thumbs');
  const resultBox = document.getElementById('recognition-results');
  let stream = null;
  let files = new DataTransfer();
  const maxImages = 5;

  function showError(message) {
    if (resultBox) {
      resultBox.innerHTML = '';
      const item = document.createElement('div');
      item.className = 'result-item result-error';
      item.textContent = message;
      resultBox.appendChild(item);
    } else {
      alert(message);
    }
  }

  async function startCamera() {
    if (stream) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      showError('Camera access is unavailable. Open this page on localhost or HTTPS and use a supported browser.');
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
      });
      video.srcObject = stream;
      await video.play();
      placeholder?.classList.add('hidden');
      if (startButton) startButton.textContent = 'Camera active';
      if (captureButton) captureButton.disabled = false;
      if (markButton) markButton.disabled = false;
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
      showError(`Could not start camera: ${error.message || 'Permission denied'}. Check browser permissions.`);
    }
  }

  function takeSnapshot() {
    if (!video.videoWidth || !video.videoHeight) throw new Error('Wait for the camera preview to start.');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d', { alpha: false });
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.9);
  }

  function updateUploads() {
    if (!imagesInput) return;
    imagesInput.files = files.files;
    if (captureCount) captureCount.textContent = String(files.files.length);
    if (thumbs) {
      thumbs.querySelectorAll('img[data-preview-url]').forEach((img) => {
        URL.revokeObjectURL(img.dataset.previewUrl);
      });
      thumbs.innerHTML = '';
      Array.from(files.files).forEach((file) => {
        const img = document.createElement('img');
        const previewUrl = URL.createObjectURL(file);
        img.alt = 'Captured face preview';
        img.src = previewUrl;
        img.dataset.previewUrl = previewUrl;
        thumbs.appendChild(img);
      });
    }
  }

  if (imagesInput) {
    imagesInput.addEventListener('change', () => {
      const selected = Array.from(imagesInput.files || []);
      if (selected.length > maxImages) {
        showError(`Choose no more than ${maxImages} images per student.`);
      }
      files = new DataTransfer();
      selected.slice(0, maxImages).forEach((file) => files.items.add(file));
      updateUploads();
    });
  }

  if (startButton) startButton.addEventListener('click', startCamera);

  if (captureButton) {
    captureButton.addEventListener('click', async () => {
      try {
        const dataUrl = takeSnapshot();
        const response = await fetch(dataUrl);
        const blob = await response.blob();
        if (files.files.length >= maxImages) {
          showError(`You can capture up to ${maxImages} images per student.`);
          return;
        }
        const file = new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' });
        files.items.add(file);
        updateUploads();
      } catch (error) {
        showError(error.message);
      }
    });
  }

  function resultRow(result) {
    const row = document.createElement('div');
    row.className = 'result-item';
    const mark = document.createElement('span');
    mark.className = `result-mark ${result.status === 'marked' ? 'good' : result.status === 'already' ? 'warn' : 'bad'}`;
    mark.textContent = result.status === 'marked' ? '✓' : result.status === 'already' ? '↻' : '×';
    const body = document.createElement('div');
    body.className = 'result-body';
    const title = document.createElement('strong');
    title.textContent = result.name ? `${result.name} (${result.student_id})` : (result.message || 'Unknown face');
    const detail = document.createElement('small');
    detail.textContent = `${result.message || ''}${result.similarity !== undefined ? ` · Similarity ${Number(result.similarity).toFixed(3)}` : ''}`;
    body.append(title, detail);
    row.append(mark, body);
    return row;
  }

  if (markButton) {
    markButton.addEventListener('click', async () => {
      const subject = document.getElementById('attendance-subject')?.value.trim();
      if (!subject) {
        showError('Enter a subject or lecture name first.');
        document.getElementById('attendance-subject')?.focus();
        return;
      }
      let image;
      try { image = takeSnapshot(); } catch (error) { showError(error.message); return; }
      markButton.disabled = true;
      markButton.textContent = 'Recognizing…';
      try {
        const token = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const response = await fetch('/api/attendance/recognize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
          body: JSON.stringify({ subject, image })
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.message || 'Recognition request failed.');
        resultBox.innerHTML = '';
        if (!payload.results?.length) showError('No face result was returned.');
        else payload.results.forEach((result) => resultBox.appendChild(resultRow(result)));
      } catch (error) {
        showError(error.message || 'Recognition failed.');
      } finally {
        markButton.disabled = false;
        markButton.innerHTML = 'Capture &amp; recognize <span>→</span>';
      }
    });
  }

  window.addEventListener('beforeunload', () => stream?.getTracks().forEach((track) => track.stop()));
})();
