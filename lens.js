const captureBtn = document.getElementById("captureBtn");
const status = document.getElementById("status");
const result = document.getElementById("result");

captureBtn.addEventListener("click", async () => {
    try {
        status.textContent = "📸 Capturing screenshot...";
        result.textContent = "";

        // Capture the visible tab
        const dataUrl = await chrome.tabs.captureVisibleTab(null, {
            format: "png"
        });

        if (!dataUrl) {
            throw new Error("Screenshot capture failed.");
        }

        status.textContent = "🔍 Sending screenshot to TruthLens...";

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
const historyItem = {
    claim: data.claim || "No claim found",
    truePercent: data.truePercent ?? 0,
    explanation: data.explanation || "No explanation available.",
    timestamp: new Date().toISOString()
};

chrome.storage.local.get({ history: [] }, (result) => {
    const history = result.history;

    history.unshift(historyItem);

    // Keep only latest 50 analyses
    chrome.storage.local.set({
        history: history.slice(0, 50)
    });
});

        status.textContent = "✅ Analysis complete";

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

        status.textContent = "❌ Capture failed";

        result.innerHTML = `
            <p class="error">
                ${escapeHtml(error.message)}
            </p>
        `;
    }
});

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
