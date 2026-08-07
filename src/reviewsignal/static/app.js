const form = document.querySelector("#prediction-form");
const textarea = document.querySelector("#review-text");
const counter = document.querySelector("#character-count");
const button = document.querySelector("#analyze-button");
const result = document.querySelector("#result");
const resultLabel = document.querySelector("#result-label");
const resultProbability = document.querySelector("#result-probability");
const resultModel = document.querySelector("#result-model");
const resultRequest = document.querySelector("#result-request");
const probabilityFill = document.querySelector("#probability-fill");

function updateCount() {
  counter.textContent = `${textarea.value.length} / 5000`;
}

function setResultState(kind, label, probability, modelVersion, requestId) {
  result.className = `result result--${kind}`;
  resultLabel.textContent = label;
  resultProbability.textContent = probability;
  resultModel.textContent = modelVersion;
  resultRequest.textContent = requestId;
  const numericProbability = Number.parseInt(probability, 10);
  probabilityFill.style.setProperty("--probability", Number.isNaN(numericProbability) ? "0%" : probability);
}

document.querySelectorAll("[data-example]").forEach((exampleButton) => {
  exampleButton.addEventListener("click", () => {
    textarea.value = exampleButton.dataset.example;
    updateCount();
    textarea.focus();
  });
});

textarea.addEventListener("input", updateCount);
updateCount();

fetch("/api/v1/model")
  .then((response) => response.json())
  .then((metadata) => {
    if (metadata.model_version) resultModel.textContent = metadata.model_version;
  })
  .catch(() => {
    resultModel.textContent = "unavailable";
  });

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = textarea.value.trim();
  if (!text) {
    setResultState("error", "Input needed", "—", resultModel.textContent, "Enter a nonblank review");
    textarea.focus();
    return;
  }

  button.disabled = true;
  button.firstChild.textContent = "Analyzing… ";
  result.setAttribute("aria-busy", "true");

  try {
    const response = await fetch("/api/v1/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Prediction unavailable");
    const probability = `${Math.round(payload.positive_probability * 100)}%`;
    setResultState(
      payload.label,
      payload.label,
      probability,
      payload.model_version,
      payload.request_id,
    );
  } catch (error) {
    setResultState("error", "Unavailable", "—", resultModel.textContent, "Please try again shortly");
  } finally {
    button.disabled = false;
    button.firstChild.textContent = "Analyze sentiment ";
    result.removeAttribute("aria-busy");
  }
});
