const captureBtn = document.getElementById("captureBtn");
const status = document.getElementById("status");
const result = document.getElementById("result");

captureBtn.addEventListener("click", async () => {
    try {
        status.textContent = " Capturing screenshot...";
        result.textContent = "";

        // Capture the visible tab
        const dataUrl = await chrome.tabs.captureVisibleTab(null, {
            format: "png"
        });

        if (!dataUrl) {
            throw new Error("Screenshot capture failed.");
        }

        status.textContent = " Sending screenshot to TruthLens...";

        // Convert screenshot to Blob
        const response = await fetch(dataUrl);
        const blob = await response.blob();

        // Create FormData
        const formData = new FormData();

        formData.append(
            "image",
            blob,
            "truthlens-screenshot.png"
        );

        // Send to FastAPI
        const apiResponse = await fetch(
            "http://127.0.0.1:5000/api/analyze-file",
            {
                method: "POST",
                body: formData
            }
        );

        if (!apiResponse.ok) {
            const errorText = await apiResponse.text();

            throw new Error(
                `Server error: ${apiResponse.status} ${errorText}`
            );
        }

        const data = await apiResponse.json();

        console.log("TruthLens response:", data);

        if (data.error) {
            throw new Error(data.error);
        }

        // Save analysis to history
        saveToHistory(data);

        status.textContent = " Analysis complete";

        result.innerHTML = `
            <div class="claim">
                <strong>Claim:</strong>
                <p>${escapeHtml(data.claim || "No claim found")}</p>
            </div>

            <div class="truth-score">
                <strong>Truth Score:</strong>
                <p>${data.truePercent ?? 0}%</p>
            </div>

            <div class="explanation">
                <strong>Explanation:</strong>
                <p>${escapeHtml(
                    data.explanation || "No explanation available."
                )}</p>
            </div>
        `;

    } catch (error) {
        console.error("Capture error:", error);

        status.textContent = " Capture failed";

        result.innerHTML = `
            <p class="error">
                ${escapeHtml(error.message)}
            </p>
        `;
    }
});

// function escapeHtml(text) {
//     const div = document.createElement("div");
//     div.textContent = text;
//     return div.innerHTML;
// }


// ============================================================
// HISTORY.............
// ============================================================

const historyBtn = document.getElementById("historyBtn");
const historyDiv = document.getElementById("history");

function saveToHistory(data) {

    const history = JSON.parse(
        localStorage.getItem("truthlens_history") || "[]"
    );
// .....
    history.unshift({
        claim: data.claim || "No claim found",
        truePercent: data.truePercent ?? 0,
        explanation: data.explanation || "No explanation available",
        timestamp: new Date().toISOString()
    });

    // Keep latest 50 analyses
    localStorage.setItem(
        "truthlens_history",
        JSON.stringify(history.slice(0, 50))
    );
}


if (historyBtn) {

    historyBtn.addEventListener("click", () => {

        const history = JSON.parse(
            localStorage.getItem("truthlens_history") || "[]"
        );

        if (!historyDiv) {
            return;
        }

        if (history.length === 0) {
            historyDiv.innerHTML = `
                <p>No history yet.</p>
            `;
            return;
        }

        historyDiv.innerHTML = history.map(item => `
            <div class="history-item">

                <strong>
                    ${escapeHtml(item.claim || "No claim found")}
                </strong>

                <p>
                    Truth Score:
                    <strong>
                        ${item.truePercent ?? 0}%
                    </strong>
                </p>

                <small>
                    ${new Date(item.timestamp).toLocaleString()}
                </small>

                <p>
                    ${escapeHtml(
                        item.explanation ||
                        "No explanation available."
                    )}
                </p>

            </div>
        `).join("");

    });

}