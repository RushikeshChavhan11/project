document.addEventListener("DOMContentLoaded", function () {
    console.log("📊 Graph Script Loaded!");

    // ✅ Populate subject dropdown on page load
    fetch('/get_subjects')
        .then(response => response.json())
        .then(subjects => {
            const subjectDropdown = document.getElementById("subject");
            subjects.forEach(subject => {
                let option = document.createElement("option");
                option.value = subject;
                option.textContent = subject;
                subjectDropdown.appendChild(option);
            });
        })
        .catch(error => console.error("❌ Error fetching subjects:", error));

    // ✅ Fetch graph data based on filters
    window.fetchGraphData = function () {
        const subject = document.getElementById("subject").value.trim();
        const totalStudents = document.getElementById("total_students").value.trim();

        if (!totalStudents || totalStudents <= 0) {
            alert("⚠ Please enter a valid total number of students.");
            return;
        }

        let url = `/get_attendance_graph?subject=${subject}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                console.log("📌 Attendance Graph Data:", data);

                const dates = data.dates;
                const presentCounts = data.present_counts;
                const totalStudentArray = Array(dates.length).fill(parseInt(totalStudents)); // Create an array of total students for each day

                // ✅ Bar Chart (Daily Attendance vs Total Students)
                const ctxBar = document.getElementById("barChart").getContext("2d");
                if (window.attendanceChart) window.attendanceChart.destroy(); // Destroy old chart before creating new one

                window.attendanceChart = new Chart(ctxBar, {
                    type: "bar",
                    data: {
                        labels: dates,
                        datasets: [
                            {
                                label: "Students Present",
                                data: presentCounts,
                                backgroundColor: "rgba(75, 192, 192, 0.6)"
                            },
                            {
                                label: "Total Students",
                                data: totalStudentArray,
                                backgroundColor: "rgba(255, 206, 86, 0.6)"
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: "top" }
                        },
                        scales: {
                            x: { title: { display: true, text: "Date" } },
                            y: { title: { display: true, text: "Number of Students" } }
                        }
                    }
                });
            })
            .catch(error => console.error("❌ Error fetching attendance graph data:", error));
    };
});


