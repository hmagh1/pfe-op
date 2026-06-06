import React, { useState } from "react";
import { uploadFile } from "../services/api";

export default function FileUpload({ label, endpoint, onNotify, onUploaded }) {
  const [status, setStatus] = useState("");

  const statusClass = status.startsWith("OK")
    ? "upload-status-ok"
    : status.startsWith("Erreur")
      ? "upload-status-error"
      : status
        ? "upload-status-wait"
        : "";

  async function handleChange(e) {
    const file = e.target.files?.[0];

    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setStatus("Erreur : le fichier doit être un .xlsx");
      if (onNotify) onNotify("error", "Le fichier doit etre au format .xlsx");
      return;
    }

    setStatus("Upload en cours...");

    try {
      const response = await uploadFile(endpoint, file);
      setStatus(`OK : ${file.name}`);
      if (onNotify) onNotify("success", `${label} upload termine.`);
      if (typeof onUploaded === "function") {
        await onUploaded(response, file);
      }
    } catch (err) {
      setStatus(`Erreur : ${err.message}`);
      if (onNotify) onNotify("error", `Erreur upload: ${err.message}`);
    }
  }

  return (
    <div className="card upload-card">
      <label>{label}</label>

      <input
        type="file"
        accept=".xlsx"
        onChange={handleChange}
      />

      <small className={statusClass}>{status}</small>
    </div>
  );
}