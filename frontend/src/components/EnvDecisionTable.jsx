import React, { useState } from "react";
import { submitDecision } from "../services/api";

export default function EnvDecisionTable({ job, env, onUpdated, onNotify }) {
  const [edits, setEdits] = useState({});
  const [reviewMode, setReviewMode] = useState({});

  function displayValue(value) {
    const text = String(value ?? "").trim();
    return text || "À compléter";
  }

  function displayPercent(value) {
    if (value === null || value === undefined || value === "") return "-";

    const num = Number(value);
    if (Number.isNaN(num)) return String(value);

    if (num <= 1) {
      return `${(num * 100).toFixed(1)}%`;
    }

    return `${num.toFixed(1)}%`;
  }

  function getSuggestionFlux(decision) {
    return (
      decision.final_flux ||
      decision.flux ||
      decision.proposed_flux ||
      decision.suggested_flux ||
      decision.ml_suggested_flux ||
      ""
    );
  }

  function getSuggestionNom(decision) {
    return (
      decision.final_nom ||
      decision.nom ||
      decision.Nom ||
      decision.proposed_nom ||
      decision.suggested_nom ||
      decision.ml_suggested_nom ||
      ""
    );
  }

  function getDestinationIp(decision) {
    return (
      decision.dst_ip ||
      decision.dstIp ||
      decision.destination_ip ||
      decision["Configured Destination"] ||
      ""
    );
  }

  function getFlowGref(decision) {
    return (
      decision.flowGrefSG ||
      decision.flow_gref_sg ||
      decision.flowGretSG ||
      decision.sg_cible ||
      decision["Configured Service"] ||
      ""
    );
  }

  function getColor(decision) {
    return decision.color || decision.niveau_securite || "";
  }

  function getDecisionKey(decision, prefix = "") {
    return `${prefix}${decision.decision_id || decision.technical_signature || Math.random()}`;
  }

  const historicalDecisions = (job?.historical_decisions || []).filter(
    (decision) => decision.env === env
  );

  const pendingDecisions = (job?.pending_decisions || []).filter(
    (decision) => decision.env === env
  );

  const hasHistorical = historicalDecisions.length > 0;
  const hasPending = pendingDecisions.length > 0;

  if (!hasHistorical && !hasPending) {
    return (
      <p className="decision-empty">
        Aucune décision en attente pour {env}.
      </p>
    );
  }

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

  function displayCell(value) {
    return <div className="cell-display">{displayValue(value)}</div>;
  }

  function editableCell(decision, field, value, placeholder = "À compléter") {
    const isEditMode = reviewMode[decision.decision_id] === "edit";

    if (!isEditMode) {
      return displayCell(value);
    }

    return (
      <textarea
        className="cell-textarea"
        defaultValue={value || ""}
        placeholder={value ? "" : placeholder}
        onChange={(e) => updateEdit(decision.decision_id, field, e.target.value)}
      />
    );
  }

  async function handleDecision(decision, action) {
    const edit = edits[decision.decision_id] || {};

    const payload = {
      decision_id: decision.decision_id,
      action,
      flux: edit.flux || getSuggestionFlux(decision) || "",
      nom: edit.nom || getSuggestionNom(decision) || "",
      extra: {
        ...edit,
        color: edit.color || getColor(decision) || "",
        niveau_securite: edit.color || getColor(decision) || "",
        flowMainSG: edit.flowMainSG || decision.flowMainSG || "",
        flowGrefSG: edit.flowGrefSG || getFlowGref(decision) || "",
        source: decision.source || "",
        historical: Boolean(
          decision.historical ||
            decision.source === "HISTORICAL_REVIEW" ||
            decision.source === "HISTORICAL_VALIDATED"
        ),
      },
    };

    try {
      const updated = await submitDecision(job.job_id, payload);
      onUpdated(updated);

      setEdits((prev) => {
        const copy = { ...prev };
        delete copy[decision.decision_id];
        return copy;
      });

      setReviewMode((prev) => {
        const copy = { ...prev };
        delete copy[decision.decision_id];
        return copy;
      });

      if (onNotify) {
        onNotify("success", "Décision enregistrée.");
      }
    } catch (err) {
      if (onNotify) {
        onNotify("error", `Erreur: ${err.message}`);
      }
    }
  }

  function renderDataRow(decision, options = {}) {
    const isHistorical = options.isHistorical === true;
    const isEditMode = reviewMode[decision.decision_id] === "edit";

    const suggestionFlux = getSuggestionFlux(decision);
    const suggestionNom = getSuggestionNom(decision);

    const statusLabel = isHistorical ? "Déjà connue" : "Nouvelle";

    const confidenceLabel = isHistorical
      ? "100.0%"
      : decision.ml_confiance
      ? displayPercent(decision.ml_confiance)
      : "N/A";

    const mlLabel = isHistorical
      ? decision.ml_modele || "historique"
      : decision.ml_modele || "-";

    return (
      <tr
        key={getDecisionKey(decision, isHistorical ? "hist-" : "pending-")}
        className={isHistorical ? "historical-row" : ""}
      >
        <td>
          <strong>{statusLabel}</strong>
        </td>

        <td>
          {mlLabel}

          {!isHistorical && decision.seuil_auto && (
            <div className="small-meta">
              seuil: {displayPercent(decision.seuil_auto)}
            </div>
          )}

          {isHistorical && <div className="small-meta">ancienne décision</div>}
        </td>

        <td>
          <strong>{confidenceLabel}</strong>

          {!isHistorical && (decision.ml_confiance || decision.seuil_auto) && (
            <div className="small-meta">
              conf={decision.ml_confiance || "-"} | seuil=
              {decision.seuil_auto || "-"}
            </div>
          )}
        </td>

        <td>
          {isEditMode ? (
            <textarea
              className="cell-textarea small"
              defaultValue={getColor(decision)}
              placeholder={getColor(decision) ? "" : "Couleur"}
              onChange={(e) =>
                updateEdit(decision.decision_id, "color", e.target.value)
              }
            />
          ) : (
            displayCell(getColor(decision))
          )}
        </td>

        <td>{displayCell(decision.src_ip)}</td>

        <td>{displayCell(getDestinationIp(decision))}</td>

        <td className="sg-col-cell">
          {editableCell(
            decision,
            "flowMainSG",
            decision.flowMainSG || "",
            "SG Source"
          )}
        </td>

        <td className="sg-col-cell">
          {editableCell(
            decision,
            "flowGrefSG",
            getFlowGref(decision),
            "SG Cible"
          )}
        </td>

        <td>{displayCell(decision.port)}</td>

        <td>
          {editableCell(decision, "flux", suggestionFlux, "Flux")}
        </td>

        <td className="nom-col-cell">
          {editableCell(decision, "nom", suggestionNom, "Nom")}
        </td>

        <td>
          <div className="action-stack">
            {!isHistorical && (
              <button
                className="btn-secondary"
                onClick={() => handleDecision(decision, "validate")}
              >
                Valider
              </button>
            )}

            <button
              className="btn-warning"
              onClick={() => {
                if (isEditMode) {
                  handleDecision(decision, "correct");
                } else {
                  setMode(decision.decision_id, "edit");
                }
              }}
            >
              {isEditMode ? "Enregistrer correction" : "Corriger"}
            </button>
          </div>
        </td>
      </tr>
    );
  }

  function renderTable(decisions, options = {}) {
    return (
      <div className="table-wrap">
        <table className="decision-table">
          <thead>
            <tr>
              <th>Statut</th>
              <th>ML</th>
              <th>Confiance</th>
              <th>Couleur</th>
              <th>Source IP</th>
              <th>Destination IP</th>
              <th className="sg-col">SG Source</th>
              <th className="sg-col">SG Cible</th>
              <th>Port</th>
              <th>Flux</th>
              <th className="nom-col">Nom</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {decisions.map((decision) => renderDataRow(decision, options))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div>
      <h3>Décisions - {env.toUpperCase()}</h3>

      {hasHistorical && (
        <section className="decision-block historical-block">
          <div className="decision-block-head">
            <h4>Lignes déjà connues</h4>
            <span>{historicalDecisions.length} ligne(s)</span>
          </div>

          <p className="decision-help">
            Ces lignes ont déjà été validées auparavant. Elles sont reprises
            automatiquement avec une confiance de 100%. Tu peux les corriger
            uniquement si nécessaire.
          </p>

          {renderTable(historicalDecisions, { isHistorical: true })}
        </section>
      )}

      {hasPending && (
        <section className="decision-block pending-block">
          <div className="decision-block-head">
            <h4>Nouvelles lignes à confirmer</h4>
            <span>{pendingDecisions.length} ligne(s)</span>
          </div>

          <p className="decision-help">
            Ces lignes doivent être validées ou corrigées avant de passer à
            l’étape suivante.
          </p>

          {renderTable(pendingDecisions, { isHistorical: false })}
        </section>
      )}
    </div>
  );
}