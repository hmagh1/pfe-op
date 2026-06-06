import React from "react";

export default function PrecheckBasicat({ precheck, loading }) {
  if (loading) {
    return (
      <div className="card">
        <h3>Contrôle BASICAT</h3>
        <p>Contrôle en cours...</p>
      </div>
    );
  }

  if (!precheck) {
    return null;
  }

  const ready = precheck.ready === true;

  return (
    <div className="card">
      <h3>Contrôle BASICAT</h3>

      <div
        style={{
          padding: "10px",
          borderRadius: "8px",
          marginBottom: "12px",
          background: ready ? "#e8f7ee" : "#fdecec",
          border: ready ? "1px solid #3bb273" : "1px solid #e55353",
        }}
      >
        <strong>
          {ready
            ? `✅ BASICAT ${precheck.basicat} prêt pour traitement`
            : `❌ BASICAT ${precheck.basicat} non prêt`}
        </strong>
      </div>

      {precheck.detected_envs && precheck.detected_envs.length > 0 && (
        <p>
          <strong>Environnement détecté :</strong>{" "}
          {precheck.detected_envs.join(", ").toUpperCase()}
        </p>
      )}

      {precheck.summary && (
        <div className="summary-grid">
          <p>
            <strong>Lignes VLISTE :</strong>{" "}
            {precheck.summary.basicat_rows ?? 0}
          </p>
          <p>
            <strong>Modèle ML :</strong>{" "}
            {precheck.summary.model_available ? "Disponible" : "Non disponible"}
          </p>
          <p>
            <strong>Versions ML :</strong>{" "}
            {precheck.summary.model_versions_count ?? 0}
          </p>
          <p>
            <strong>Décisions historiques :</strong>{" "}
            {precheck.summary.historical_decisions_count ?? 0}
          </p>
        </div>
      )}

      {precheck.errors && precheck.errors.length > 0 && (
        <div className="error-box">
          <strong>Erreurs :</strong>
          <ul>
            {precheck.errors.map((err, index) => (
              <li key={index}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {precheck.warnings && precheck.warnings.length > 0 && (
        <div className="warning-box">
          <strong>Avertissements :</strong>
          <ul>
            {precheck.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Contrôle</th>
              <th>Résultat</th>
              <th>Détail</th>
            </tr>
          </thead>
          <tbody>
            {(precheck.checks || []).map((check, index) => (
              <tr key={index}>
                <td>{check.name}</td>
                <td>{check.ok ? "✅ OK" : "❌ KO"}</td>
                <td>{check.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}