"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = { bootstrap: null, jobs: [], selected: null, selectedImages: new Set(), submitting: false, connected: false, busy: false, timer: null, detailSequence: 0, historySignature: "", detailsSignature: "", startingId: null };
  const activeStatuses = new Set(["queued", "running"]);
  const knownVariants = new Set(["clerg", "adams", "fan2005", "levelset"]);
  const familySpecs = {
    gaussian_noise: { values: [2, 8], unit: "σ, intensity", min: 0, max: 255, step: "any" },
    gaussian_blur: { values: [0.5, 1.5], unit: "σ, pixels", min: 0, max: 30, step: "any" },
    salt_pepper: { values: [0.005, 0.02], unit: "fraction", min: 0, max: 1, step: "any" },
    jpeg: { values: [90, 50], unit: "quality, 1–100", min: 1, max: 100, step: "1" },
    brightness_scale: { values: [0.8, 1.2], unit: "multiplier", min: 0.01, max: 10, step: "any" }
  };

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }
  function message(id, text) { $(id).textContent = text || ""; $(id).hidden = !text; }
  function safeUrl(value) {
    if (typeof value !== "string" || !value) return null;
    try {
      const url = new URL(value, window.location.origin);
      return url.origin === window.location.origin && ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (_) { return null; }
  }
  function link(label, url, newTab = false) {
    const href = safeUrl(url);
    if (!href) return null;
    const a = node("a", "", label);
    a.href = href;
    if (newTab) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
    return a;
  }
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, { cache: "no-store", ...options, signal: controller.signal });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`); }
      if (!response.ok) throw new Error(data.error || `Request failed (HTTP ${response.status}).`);
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The server did not respond in time. Refresh to check whether the run was accepted.");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function checked(name) { return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value); }
  function labelFor(kind, id) { return state.bootstrap?.[kind]?.find((item) => item.id === id)?.label || id || "—"; }
  function formatNumber(value, digits = 4) {
    if (value === null || value === undefined || value === "" || typeof value === "boolean") return "—";
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(digits) : "—";
  }
  function formatDate(value) {
    if (!value) return "Time unavailable";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function connection(ok) {
    state.connected = ok;
    const ready = ok && state.bootstrap?.ready;
    $("connection-dot").className = `dot ${ok ? ready ? "ready" : "" : "offline"}`;
    $("connection-status").textContent = ok ? ready ? "Local runner ready" : "Runner not ready" : "Connection unavailable";
    updateControls();
  }
  function updateControls() {
    const n = state.selectedImages.size;
    const variants = checked("variants");
    const families = checked("families");
    $("selection-count").textContent = `${n} selected`;
    $("run-summary").textContent = `${n} images · ${variants.length} algorithm${variants.length === 1 ? "" : "s"} · ${families.length} perturbation ${families.length === 1 ? "family" : "families"} · ${$("replicates").value} random replicates`;
    let reason = "Ready to start. Nothing runs until you press the button.";
    if (state.submitting) reason = "Submitting your evaluation…";
    else if (!state.connected) reason = "Connect to the local runner before starting.";
    else if (!state.bootstrap?.ready) reason = state.bootstrap?.message || "The runner is not ready.";
    else if (state.startingId || state.jobs.some((job) => activeStatuses.has(job.status))) reason = "An evaluation is active. Wait for it to finish before starting another.";
    else if (n < 2 || n > 20) reason = "Select between 2 and 20 images.";
    else if (!variants.length) reason = "Select at least one algorithm.";
    else if (!families.length) reason = "Select at least one perturbation family.";
    const allowed = state.connected && state.bootstrap?.ready && !state.submitting && !state.startingId && !state.jobs.some((job) => activeStatuses.has(job.status)) && n >= 2 && n <= 20 && variants.length && families.length;
    $("start-run").disabled = !allowed;
    $("run-reason").textContent = reason;
    $("start-run").firstChild.textContent = state.submitting ? "Submitting… " : "Start evaluation ";
  }
  function imageIds() { return (state.bootstrap?.images?.[$("split").value] || []).map(String); }
  function renderImages() {
    const query = $("image-search").value.trim().toLowerCase();
    const ids = imageIds().filter((id) => id.toLowerCase().includes(query));
    const fragment = document.createDocumentFragment();
    for (const id of ids) {
      const label = node("label", "image-choice");
      const input = node("input"); input.type = "checkbox"; input.value = id; input.checked = state.selectedImages.has(id); input.setAttribute("aria-label", `Select image ${id}`);
      const image = node("img"); image.src = `/api/image?${new URLSearchParams({ split: $("split").value, id })}`; image.alt = `Image ${id}`; image.loading = "lazy"; image.decoding = "async";
      image.addEventListener("error", () => { label.classList.add("unavailable"); image.alt = `Preview unavailable: ${id}`; label.title = "Preview unavailable. The runner will validate this image."; });
      input.addEventListener("change", () => {
        if (input.checked && state.selectedImages.size >= 20) { input.checked = false; $("image-note").textContent = "20-image limit reached. Deselect an image to choose another."; return; }
        if (input.checked) state.selectedImages.add(id); else state.selectedImages.delete(id);
        $("image-note").textContent = `${imageIds().length} images available. Selections remain when filtering.`;
        updateControls();
      });
      label.append(image, input, node("span", "", id)); fragment.append(label);
    }
    if (!ids.length) fragment.append(node("p", "hint", query ? "No matching image IDs." : "No images available for this split."));
    $("image-grid").replaceChildren(fragment);
    $("image-note").textContent = `${ids.length} of ${imageIds().length} images shown. Selections remain when filtering.`;
    updateControls();
  }
  function initializeOptions() {
    const variants = document.createDocumentFragment();
    for (const item of state.bootstrap.variants || []) {
      if (!knownVariants.has(item.id)) continue;
      const label = node("label", "check-option"); const input = node("input"); input.type = "checkbox"; input.name = "variants"; input.value = item.id; input.checked = item.id === "clerg";
      label.append(input, node("span", "", item.label)); variants.append(label);
    }
    $("variant-options").replaceChildren(variants);
    const families = document.createDocumentFragment();
    for (const item of state.bootstrap.families || []) {
      const spec = familySpecs[item.id]; if (!spec) continue;
      const family = node("div", "family"); const label = node("label", "family-header"); const input = node("input"); input.type = "checkbox"; input.name = "families"; input.value = item.id; input.checked = item.id === "gaussian_noise";
      label.append(input, node("span", "", item.label));
      const fields = node("div", "severity-fields"); fields.hidden = !input.checked;
      spec.values.forEach((value, i) => {
        const fieldLabel = node("label", "", `Level ${i + 1} · ${spec.unit}`);
        const field = node("input"); field.type = "number"; field.id = `${item.id}-${i}`; field.value = value; field.min = spec.min; field.max = spec.max; field.step = spec.step; field.required = true; field.disabled = !input.checked;
        fieldLabel.append(field); fields.append(fieldLabel);
      });
      input.addEventListener("change", () => { fields.hidden = !input.checked; fields.querySelectorAll("input").forEach((field) => { field.disabled = !input.checked; }); });
      family.append(label, fields); families.append(family);
    }
    $("family-options").replaceChildren(families);
    const reports = document.createDocumentFragment();
    for (const report of state.bootstrap.frozen_reports || []) { const a = link(report.label, report.url, true); if (a) reports.append(a); }
    if (!reports.childNodes.length) reports.append(node("p", "hint", "No frozen report links are available."));
    $("frozen-reports").replaceChildren(reports);
    state.selectedImages = new Set(imageIds().slice(0, 2));
    renderImages();
  }
  function renderHistory() {
    $("job-count").textContent = state.jobs.length;
    const signature = JSON.stringify([state.selected, state.jobs.map(({ id, label, status, created_at }) => ({ id, label, status, created_at }))]);
    if (signature === state.historySignature) return;
    state.historySignature = signature;
    const fragment = document.createDocumentFragment();
    for (const job of state.jobs) {
      const button = node("button", "job-tab"); button.type = "button"; button.setAttribute("aria-pressed", String(job.id === state.selected));
      const status = activeStatuses.has(job.status) || ["complete", "failed", "interrupted"].includes(job.status) ? job.status : "unknown";
      button.append(node("strong", "", job.label || job.id), node("span", `status-badge ${status}`, status), node("small", "", formatDate(job.created_at)));
      button.addEventListener("click", () => { state.selected = job.id; state.detailsSignature = ""; renderHistory(); renderJob(job); fetchDetail(job.id); });
      fragment.append(button);
    }
    if (!state.jobs.length) fragment.append(node("p", "hint", "No local evaluations yet. Configure a run on the left to get started."));
    $("job-history").replaceChildren(fragment);
  }
  function renderJob(job) {
    if (!job || job.id !== state.selected) return;
    $("empty-state").hidden = true; $("job-detail").hidden = false;
    $("job-title").textContent = job.label || job.id;
    $("job-date").textContent = `${formatDate(job.created_at)} · ${job.id}`;
    const status = activeStatuses.has(job.status) || ["complete", "failed", "interrupted"].includes(job.status) ? job.status : "unknown";
    $("job-status").className = `status-badge ${status}`; $("job-status").textContent = status;
    $("job-stage").textContent = job.stage || (job.status === "queued" ? "Waiting for the runner" : job.status);
    const written = Number(job.records_written) || 0, expected = Number(job.expected_records) || 0;
    const percentage = expected > 0 ? Math.max(0, Math.min(100, Math.round(written / expected * 100))) : 0;
    $("job-progress").value = percentage;
    $("progress-text").textContent = expected > 0 ? `${written} / ${expected} records · ${percentage}%` : `${written} records`;
    message("job-error", job.error || (job.status === "interrupted" ? "This run was interrupted. Its existing output is retained; you can start a new evaluation." : job.preview_error ? `Preview generation issue: ${job.preview_error}. The evaluation output is available separately.` : ""));
    $("metric-images").textContent = job.n_images ?? "—";
    $("metric-variants").textContent = job.n_variants ?? "—";
    $("metric-families").textContent = job.n_families ?? "—";
    $("metric-p").textContent = formatNumber(job.minimum_p, 4);
    $("inference-note").textContent = `Image n = ${job.n_images ?? "—"}; images are the sampling units. Holm family size = ${job.n_variants ?? "—"} selected algorithms. With two images, the minimum raw p is 0.5. Interface colors do not indicate statistical significance.`;
    const signature = JSON.stringify([job.id, job.report_url, job.downloads, job.results, job.preview, job.status]);
    if (signature !== state.detailsSignature) {
      state.detailsSignature = signature;
      const actions = document.createDocumentFragment();
      if (job.report_url) { const report = link("Open report ↗", job.report_url, true); if (report) actions.append(report); }
      for (const download of job.downloads || []) { const a = link(download.label, download.url); if (a) { a.download = ""; actions.append(a); } }
      $("job-actions").replaceChildren(actions);
      const results = Array.isArray(job.results) ? job.results : [];
      $("results-empty").hidden = results.length > 0; $("results-table-wrap").hidden = !results.length;
      $("results-empty").textContent = ["failed", "interrupted"].includes(job.status) ? "This run did not finish. Check its error and runner log; any available partial output is linked above." : job.status === "complete" ? "This evaluation has no summary rows. Check the report or downloaded output." : "Results will appear after the evaluation finishes.";
      const rows = document.createDocumentFragment();
      for (const result of results) {
        const tr = node("tr"), name = node("td"); name.append(node("strong", "", labelFor("variants", result.variant)), node("span", "", labelFor("families", result.corruption_family)));
        tr.append(name, node("td", "", formatNumber(result.mean)), node("td", "", `${formatNumber(result.ci95_low)} to ${formatNumber(result.ci95_high)}`), node("td", "", formatNumber(result.holm_p)));
        rows.append(tr);
      }
      $("results-body").replaceChildren(rows);
      const previews = document.createDocumentFragment();
      for (const preview of job.preview || []) {
        const a = link("", preview.url, true); if (!a) continue;
        const figure = node("figure"), img = node("img"); img.src = a.href; img.alt = preview.label || "Evaluation preview"; img.loading = "lazy";
        a.append(img); figure.append(a, node("figcaption", "", preview.label)); previews.append(figure);
      }
      $("previews-panel").hidden = !previews.childNodes.length; $("previews").replaceChildren(previews);
    }
    if (Object.prototype.hasOwnProperty.call(job, "log_tail")) $("log-tail").textContent = Array.isArray(job.log_tail) ? job.log_tail.join("\n") : job.log_tail || "No log output available.";
    else $("log-tail").textContent = "Loading runner log…";
  }
  async function fetchDetail(id) {
    if (document.hidden) return;
    const sequence = ++state.detailSequence;
    try {
      const job = await request(`/api/jobs/${encodeURIComponent(id)}`);
      if (sequence === state.detailSequence && state.selected === id) renderJob(job);
    } catch (error) {
      if (sequence === state.detailSequence && state.selected === id) message("connection-error", `Could not refresh the selected run: ${error.message}`);
    }
  }
  async function refresh(forceBootstrap = false) {
    if (state.busy || document.hidden) return;
    state.busy = true; $("refresh").disabled = true; clearTimeout(state.timer);
    try {
      if (!state.bootstrap || !state.bootstrap.ready || !state.connected || forceBootstrap === true) {
        const firstLoad = !state.bootstrap;
        const bootstrap = await request("/api/bootstrap");
        state.bootstrap = bootstrap; $("version").textContent = bootstrap.version ? `v${String(bootstrap.version).replace(/^v/, "")}` : "";
        if (firstLoad) initializeOptions();
      }
      const data = await request("/api/jobs");
      if (!Array.isArray(data.jobs)) throw new Error("The server returned invalid run history.");
      const previous = new Map(state.jobs.map((job) => [job.id, job.status]));
      state.jobs = data.jobs;
      if (state.startingId && state.jobs.some((job) => job.id === state.startingId)) state.startingId = null;
      const justCompleted = state.jobs.find((job) => job.status === "complete" && activeStatuses.has(previous.get(job.id)));
      if (justCompleted) state.selected = justCompleted.id;
      else if (!state.selected || !state.jobs.some((job) => job.id === state.selected)) state.selected = state.jobs.find((job) => activeStatuses.has(job.status))?.id || state.jobs[0]?.id || null;
      connection(true); message("connection-error", ""); renderHistory();
      if (state.selected) { renderJob(state.jobs.find((job) => job.id === state.selected)); await fetchDetail(state.selected); }
      else { $("empty-state").hidden = false; $("job-detail").hidden = true; }
    } catch (error) { connection(false); message("connection-error", `Local runner unavailable: ${error.message} Your settings are preserved. Use Refresh to retry.`); }
    finally { state.busy = false; $("refresh").disabled = false; if (!document.hidden) state.timer = setTimeout(refresh, 3000); }
  }
  $("run-form").addEventListener("change", updateControls);
  $("split").addEventListener("change", () => { state.selectedImages = new Set(imageIds().slice(0, 2)); $("image-search").value = ""; renderImages(); });
  $("image-search").addEventListener("input", renderImages);
  $("first-two").addEventListener("click", () => { state.selectedImages = new Set(imageIds().slice(0, 2)); renderImages(); });
  $("clear-images").addEventListener("click", () => { state.selectedImages.clear(); renderImages(); });
  $("refresh").addEventListener("click", () => refresh(true));
  $("run-form").addEventListener("submit", async (event) => {
    event.preventDefault(); updateControls(); if ($("start-run").disabled || !$("run-form").reportValidity()) return;
    const families = checked("families"), severities = {};
    for (const family of families) {
      severities[family] = [0, 1].map((i) => Number($(`${family}-${i}`).value));
      if (severities[family][0] === severities[family][1]) { message("form-error", "Use two different severity values for each selected family."); return; }
    }
    const payload = { label: $("run-label").value.trim(), split: $("split").value, image_ids: [...state.selectedImages], max_dimension: Number($("max-dimension").value), variants: checked("variants"), seed_policy: $("seed-policy").value, families, severities, replicates: Number($("replicates").value) };
    state.submitting = true; updateControls(); message("form-error", "");
    try {
      const data = await request("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json", "X-MonoGrow-Token": state.bootstrap.token }, body: JSON.stringify(payload) });
      if (!data.job_id) throw new Error("No run ID was returned. Refresh before trying again.");
      state.selected = data.job_id; state.startingId = data.job_id; state.detailsSignature = "";
      $("workspace").focus({ preventScroll: true });
      if (window.matchMedia("(max-width: 760px)").matches) $("workspace").scrollIntoView({ behavior: "auto", block: "start" });
    } catch (error) { connection(false); message("form-error", `The run could not be confirmed: ${error.message} Your configuration has not been cleared.`); }
    finally { state.submitting = false; updateControls(); await refresh(true); }
  });
  document.addEventListener("visibilitychange", () => { clearTimeout(state.timer); if (!document.hidden) refresh(); });
  refresh();
})();
