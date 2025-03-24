const captureButton = document.getElementById('captureButton');
const videoContainer = document.getElementById('video-container');
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const takePhotoButton = document.getElementById('takePhotoButton');
const capturedImage = document.getElementById('capturedImage');

// Show webcam on clicking "Capture Image"
captureButton.addEventListener('click', () => {
    videoContainer.style.display = 'flex'; // Show the video container

    // Start webcam
    navigator.mediaDevices.getUserMedia({ video: true })
        .then((stream) => {
            video.srcObject = stream;
        })
        .catch((error) => {
            console.error('Error accessing webcam: ', error);
            alert('Unable to access the webcam.');
        });
});

// Capture image from webcam
takePhotoButton.addEventListener('click', () => {
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert canvas image to Base64
    const imageData = canvas.toDataURL('image/png');
    capturedImage.value = imageData;

    // Stop webcam stream after capturing image
    video.srcObject.getTracks().forEach(track => track.stop());

    alert('Image captured successfully! You can now submit the form.');

    // Hide video & show captured image preview
    video.style.display = 'none';
    takePhotoButton.style.display = 'none';
    canvas.style.display = 'block';
});

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('capture-button').disabled = false; // ✅ Enable button on page load

    document.querySelectorAll('.mark-btn').forEach(button => {
        button.addEventListener('click', () => openWebcam(button));
    });

    document.getElementById('capture-button').addEventListener('click', captureAttendance);
});

document.addEventListener("DOMContentLoaded", function() {
    fetch('/get_subjects')
    .then(response => response.json())
    .then(subjects => {
        console.log("🔹 Subjects Fetched:", subjects);  // ✅ Debugging
        let subjectDropdown = document.getElementById("subject");

        if (!subjects.length) {
            console.error("❌ No subjects received from the server.");
            return;
        }

        subjects.forEach(subject => {
            let option = document.createElement("option");
            option.value = subject;
            option.textContent = subject;
            subjectDropdown.appendChild(option);
        });
    })
    .catch(error => console.error("❌ Error fetching subjects:", error));
});


function trainImages() {
    document.getElementById("trainStatus").innerHTML = "⏳ Training started...";

    fetch('/train_images', {
        method: 'POST',  // ✅ This ensures it sends a POST request
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})  // ✅ Send an empty JSON body
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            document.getElementById("trainStatus").innerHTML = "✅ Training completed successfully!";
        } else {
            document.getElementById("trainStatus").innerHTML = `❌ Error: ${data.message}`;
        }
    })
    .catch(error => {
        document.getElementById("trainStatus").innerHTML = "⚠ Error training images.";
        console.error("❌ Error:", error);
    });
}
