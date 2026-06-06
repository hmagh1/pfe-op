const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:18000/api";

async function readError(res) {
  const text = await res.text();

  try {
    const parsed = JSON.parse(text);
    return parsed.detail || parsed.message || text;
  } catch {
    return text;
  }
}

export async function uploadFile(endpoint, file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function createJob(basicat) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ basicat }),
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function listJobs() {
  const res = await fetch(`${API_BASE}/jobs`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function getJobDecisionsHistory(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/decisions-history`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function resetJobs() {
  const res = await fetch(`${API_BASE}/admin/reset-jobs`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function runFrJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/run-fr`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function runSnifJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/run-snif`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function runSnifEnvJob(jobId, envName) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/run-snif/${envName}`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function finalizeMafJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/finalize-maf`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function submitDecision(jobId, payload) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function listOutputs() {
  const res = await fetch(`${API_BASE}/outputs`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export function downloadUrl(path) {
  return `${API_BASE}/download/${path}`;
}

export async function getSnifPreview(jobId, envName) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/snif-preview/${envName}`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function skipSnifEnvJob(jobId, envName) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/skip-snif/${envName}`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function completeSnifReview(jobId, envName) {
  const res = await fetch(
    `${API_BASE}/jobs/${jobId}/complete-snif-review/${envName}`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function trainModel() {
  const res = await fetch(`${API_BASE}/ml/train`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function listModelVersions() {
  const res = await fetch(`${API_BASE}/ml/model-versions`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function getDecisionStats() {
  const res = await fetch(`${API_BASE}/ml/decision-stats`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}
export async function precheckBasicat(basicat) {
  const res = await fetch(`${API_BASE}/precheck-basicat/${encodeURIComponent(basicat)}`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}
export async function promoteModel(modelId) {
  const res = await fetch(`${API_BASE}/ml/promote-model/${encodeURIComponent(modelId)}`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}

export async function getActiveModel() {
  const res = await fetch(`${API_BASE}/ml/active-model`);

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}
export async function askRag(question) {
  const res = await fetch(`${API_BASE}/rag/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) {
    throw new Error(await readError(res));
  }

  return res.json();
}