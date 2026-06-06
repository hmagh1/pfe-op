import React, { useState } from "react";
import { getSnifPreview } from "../services/api";

export default function SnifPreviewBox({ job, env, onNotify }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);

  const envLabel = String(env || "").toUpperCase();

  async function loadPreview() {
    if (!job?.job_id) return;

    try {
      setLoading(true);
      const data = await getSnifPreview(job.job_id, env);
      setPreview(data);

      if (onNotify) {
        onNotify("success", `applications_ip chargé pour ${envLabel}`);
      }
    } catch (err) {
      if (onNotify) {
        onNotify("error", err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function copyQuery() {
    const query = preview?.query || "";

    if (!query) {
      if (onNotify) onNotify("error", "Aucune requête à copier.");
      return;
    }

    try {
      await navigator.clipboard.writeText(query);
      if (onNotify) onNotify("success", "Requête copiée.");
    } catch {
      if (onNotify) onNotify("error", "Impossible de copier la requête.");
    }
  }

  return (
    <div className="snif-preview-box">
      <div className="snif-preview-actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={loadPreview}
          disabled={loading}
        >
          {loading ? "Chargement..." : "Afficher applications_ip"}
        </button>

        {preview?.query && (
          <button
            type="button"
            className="btn-warning"
            onClick={copyQuery}
          >
            Copier la requête
          </button>
        )}
      </div>

      {preview && (
        <div className="snif-preview-content">
          <p>
            <strong>Fichier :</strong>{" "}
            {preview.path || "applications_ip.xlsx introuvable"}
          </p>

          <label>
            <strong>Requête à coller dans l’outil de recherche</strong>
          </label>

          <textarea
            readOnly
            value={preview.query || ""}
            rows={4}
            className="snif-query-textarea"
            placeholder="Aucune VM trouvée dans applications_ip."
          />

          {preview.head && preview.head.length > 0 && (
            <div className="table-wrap snif-preview-table">
              <table>
                <thead>
                  <tr>
                    {Object.keys(preview.head[0]).map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {preview.head.map((row, index) => (
                    <tr key={index}>
                      {Object.keys(preview.head[0]).map((col) => (
                        <td key={col}>{String(row[col] ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.head && preview.head.length === 0 && (
            <p className="decision-empty">
              Aucune donnée trouvée dans applications_ip.
            </p>
          )}
        </div>
      )}
    </div>
  );
}