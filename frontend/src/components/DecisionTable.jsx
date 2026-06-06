import React, { useState } from "react";
import { submitDecision } from "../services/api";

export default function DecisionTable({ job, onUpdated, onNotify }) {
  const [edits, setEdits] = useState({});
  const [reviewMode, setReviewMode] = useState({});

  function displayValue(value) {
    const text = String(value ?? "").trim();
    return text || "À compléter";
  }

  if (!job?.pending_decisions?.length) {
    return <p className="decision-empty">Aucune decision en attente.</p>;
  }

  const validated = (job.pending_decisions || []).filter(
    (d) => Number(d.score) >= 99 || d.score === "100"
  );
  const pending = (job.pending_decisions || []).filter(
    (d) => !(Number(d.score) >= 99 || d.score === "100")
  );

  function updateEdit(id, field, value) {
    setEdits((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || {}),
        [field]: value,
      },
    }));
  }

  function setMode(id, mode) {
    setReviewMode((prev) => ({
      ...prev,
      [id]: mode,
    }));
  }

  async function handleDecision(decision, action) {
    const edit = edits[decision.decision_id] || {};

    const payload = {
      decision_id: decision.decision_id,
      action,
      flux: edit.flux || decision.proposed_flux || decision.suggested_flux || "",
      nom: edit.nom || decision.proposed_nom || decision.suggested_nom || "",
      extra: edit,
    };

    try {
      const updated = await submitDecision(job.job_id, payload);
      onUpdated(updated);
      if (onNotify) onNotify("success", "Decision enregistree.");
    } catch (err) {
      if (onNotify) onNotify("error", `Erreur: ${err.message}`);
    }
  }

  return (
    <div>
      <h2>Decisions a valider</h2>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Env</th>
              <th>Score</th>
              <th>Score préd.</th>
              <th>Couleur</th>
              <th>Source IP</th>
              <th>Destination IP</th>
              <th>SG Source</th>
              <th>SG Cible</th>
              <th>Port</th>
              <th>Flux</th>
              <th>Nom</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {validated.length > 0 && (
              <>
                <tr>
                  <td colSpan={12} className="validated-header">
                    Lignes validées et traitées
                  </td>
                </tr>
                {validated.map((d) => (
                  <React.Fragment key={d.decision_id}>
                    <tr className="validated-message">
                      <td colSpan={12}>Validée et traitée</td>
                    </tr>
                    <tr className="validated-row">
                      <td>{d.env}</td>
                      <td>{"100"}</td>
                      <td>{d.ml_confiance || d.score || "100"}</td>
                      <td>
                        {(d.color || d.niveau_securite || "White") +
                          (d.ml_confiance ? ` (${d.ml_confiance})` : d.score ? ` (${d.score})` : "")}
                      </td>
                      <td>{displayValue(d.src_ip)}</td>
                      <td>{displayValue(d.dst_ip || d.dstIp || d.destination_ip || d["Configured Destination"])}</td>
                      <td>{displayValue(d.flowMainSG)}</td>
                      <td>{displayValue(d.flowGrefSG || d.flow_gref_sg || d.flowGretSG || d.sg_cible || d["Configured Service"])}</td>
                      <td>{displayValue(d.port)}</td>
                      <td>
                        <input defaultValue={d.proposed_flux || d.suggested_flux || ""} disabled />
                      </td>
                      <td>
                        <input defaultValue={d.proposed_nom || d.suggested_nom || ""} disabled />
                      </td>
                      <td />
                    </tr>
                  </React.Fragment>
                ))}
              </>
            )}

            {pending.map((d) => (
              <tr key={d.decision_id}>
                <td>{d.env}</td>
                <td>{d.score}</td>
                <td>{d.ml_confiance || "-"}</td>
                <td>
                  {(d.color || d.niveau_securite || "Grey") +
                    (d.ml_confiance ? ` (${d.ml_confiance})` : d.score ? ` (${d.score})` : "")}
                </td>
                <td>{displayValue(d.src_ip)}</td>
                <td>{displayValue(d.dst_ip || d.dstIp || d.destination_ip || d["Configured Destination"])}</td>
                <td>
                  <input
                    defaultValue={d.flowMainSG || ""}
                    disabled={reviewMode[d.decision_id] !== "edit"}
                    placeholder={d.flowMainSG ? "" : "À compléter"}
                    onChange={(e) => updateEdit(d.decision_id, "flowMainSG", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    defaultValue={d.flowGrefSG || d.flow_gref_sg || d.flowGretSG || d.sg_cible || ""}
                    disabled={reviewMode[d.decision_id] !== "edit"}
                    placeholder={d.flowGrefSG ? "" : "À compléter"}
                    onChange={(e) => updateEdit(d.decision_id, "flowGrefSG", e.target.value)}
                  />
                </td>
                <td>{displayValue(d.port)}</td>

                <td>
                  <input
                    defaultValue={d.proposed_flux || d.suggested_flux || ""}
                    disabled={reviewMode[d.decision_id] !== "edit"}
                    placeholder={d.suggested_flux ? `Suggestion: ${d.suggested_flux}` : "À compléter"}
                    onChange={(e) => updateEdit(d.decision_id, "flux", e.target.value)}
                  />
                <td>
                  <input
                    defaultValue={d.color || d.niveau_securite || ""}
                    disabled={reviewMode[d.decision_id] !== "edit"}
                    placeholder={d.color || d.niveau_securite ? "" : "Couleur"}
                    onChange={(e) => updateEdit(d.decision_id, "color", e.target.value)}
                  />
                  <div className="small-meta">{d.ml_confiance ? `(${d.ml_confiance})` : d.score ? `(${d.score})` : ""}</div>
                </td>
                    defaultValue={d.proposed_nom || d.suggested_nom || ""}
                    disabled={reviewMode[d.decision_id] !== "edit"}
                    placeholder={d.suggested_nom ? `Suggestion: ${d.suggested_nom}` : "À compléter"}
                    onChange={(e) => updateEdit(d.decision_id, "nom", e.target.value)}
                  />
                </td>

                <td>
                  {(d.ml_confiance || d.seuil_auto) && (
                    <p className="decision-meta">
                      confiance={d.ml_confiance || "-"} | seuil_auto={d.seuil_auto || "-"}
                    </p>
                  )}

                  <div className="action-stack">
                    <button className="btn-secondary" onClick={() => handleDecision(d, "validate")}>
                      Valider
                    </button>

                    <button
                      className="btn-warning"
                      onClick={() => {
                        if (reviewMode[d.decision_id] === "edit") {
                          handleDecision(d, "correct");
                        } else {
                          setMode(d.decision_id, "edit");
                        }
                      }}
                    >
                      Non (corriger)
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
