document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ Attendance script loaded!");

    // Function to fetch attendance records
    window.fetchAttendance = function () {
        const studentId = document.getElementById("student").value.trim();
        const subject = document.getElementById("subject");
        const date = document.getElementById("date").value.trim();
        const attendanceTable = document.getElementById("attendance-table");

        // 🚀 Check if all inputs are empty
        if (!studentId && !subject && !date) {
            alert("⚠ Please enter at least one filter (Student ID, Subject, or Date).");
            attendanceTable.innerHTML = '<tr><td colspan="6" class="no-data">⚠ Please enter at least one filter.</td></tr>';
            return;
        }

        // Clear previous results
        attendanceTable.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';

        // Construct query parameters
        let queryParams = [];
        if (studentId) queryParams.push(`student_id=${studentId}`);
        if (subject) queryParams.push(`subject=${subject}`);
        if (date) queryParams.push(`date=${date}`);

        let url = "/get_attendance";
        if (queryParams.length > 0) {
            url += "?" + queryParams.join("&");
        }

        // Fetch attendance data
        fetch(url)
            .then(response => response.json())
            .then(data => {
                console.log("📌 Attendance Data:", data);
                attendanceTable.innerHTML = "";

                if (data.length === 0) {
                    attendanceTable.innerHTML = '<tr><td colspan="6" class="no-data">❌ No records found.</td></tr>';
                    return;
                }

                // Populate table with attendance records
                data.forEach(record => {
                    const row = `<tr>
                        <td>${record.student_id}</td>
                        <td>${record.name}</td>
                        <td>${record.subject}</td>
                        <td>${record.date}</td>
                        <td>${record.time}</td>
                        <td class="${record.status.toLowerCase()}">${record.status}</td>
                    </tr>`;
                    attendanceTable.innerHTML += row;
                });
            })
            .catch(error => {
                console.error("❌ Error fetching attendance:", error);
                attendanceTable.innerHTML = '<tr><td colspan="6" class="no-data">⚠ Error fetching records.</td></tr>';
            });
    };

    // Function to download attendance as CSV
    window.downloadCSV = function () {
        window.location.href = "/download_attendance";
    };
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
