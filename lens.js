const captureBtn = document.getElementById("captureBtn");
const status = document.getElementById("status");
const result = document.getElementById("result");

captureBtn.addEventListener("click", async () => {
    try {
        // Show status
        status.textContent = "📸 Capturing screenshot...";
        result.textContent = "";

        // Get the current active tab
        const tabs = await chrome.tabs.query({
            active: true,
            currentWindow: true
        });

        if (!tabs || tabs.length === 0) {
            throw new Error("No active tab found.");
        }

        // Capture visible part of the current tab
        chrome.tabs.captureVisibleTab(
            null,
            {
                format: "png"
            },
            async (dataUrl) => {

                if (chrome.runtime.lastError) {
                    throw new Error(
                        chrome.runtime.lastError.message
                    );
                }

                try {
                    status.textContent =
                        "🔍 Sending screenshot to TruthLens...";

                    // Convert base64 screenshot into Blob
                    const response = await fetch(dataUrl);

                    const blob = await response.blob();

                    // Create FormData
                    const formData = new FormData();

                    formData.append(
                        "image",
                        blob,
                        "truthlens-screenshot.png"
                    );

                    // Send screenshot to FastAPI
                    const apiResponse = await fetch(
                        "http://127.0.0.1:5000/api/analyze-file",
                        {
                            method: "POST",
                            body: formData
                        }
                    );

                    // Check server response
                    if (!apiResponse.ok) {
                        const errorText =
                            await apiResponse.text();

                        throw new Error(
                            `Server error: ${apiResponse.status} ${errorText}`
                        );
                    }

                    const data =
                        await apiResponse.json();

                    console.log("TruthLens response:", data);

                    // Check for backend error
                    if (data.error) {
                        throw new Error(data.error);
                    }

                    // Display result
                    status.textContent =
                        "✅ Analysis complete";

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
                                data.explanation ||
                                "No explanation available."
                            )}</p>
                        </div>
                    `;

                } catch (error) {

                    console.error(error);

                    status.textContent =
                        "❌ Analysis failed";

                    result.innerHTML = `
                        <p class="error">
                            ${escapeHtml(error.message)}
                        </p>
                    `;
                }
            }
        );

    } catch (error) {

        console.error(error);

        status.textContent =
            "❌ Screenshot failed";

        result.innerHTML = `
            <p class="error">
                ${escapeHtml(error.message)}
            </p>
        `;
    }
});


// ============================================================
// Prevent HTML from being inserted directly into the popup
// ============================================================

function escapeHtml(text) {

    const div = document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}