import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import FileUpload from "./components/FileUpload";
import EnvDecisionTable from "./components/EnvDecisionTable";
import SnifPreviewBox from "./components/SnifPreviewBox";
import {
  createJob,
  getJob,
  resetJobs,
  runFrJob,
  runSnifEnvJob,
  finalizeMafJob,
  skipSnifEnvJob,
  listJobs,
  getJobDecisionsHistory,
  trainModel,
  listModelVersions,
  getDecisionStats,
  completeSnifReview,
} from "./services/api";
import "./style.css";

function App() {
  const [basicat, setBasicat] = useState("");
  const [job, setJob] = useState(null);
  const [basicatError, setBasicatError] = useState("");
  const [toasts, setToasts] = useState([]);

  const [jobHistory, setJobHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const [jobDecisionsHistory, setJobDecisionsHistory] = useState([]);
  const [decisionsHistoryLoading, setDecisionsHistoryLoading] = useState(false);
  const [selectedHistoryJobId, setSelectedHistoryJobId] = useState("");

  const [mlTrainingLoading, setMlTrainingLoading] = useState(false);
  const [mlTrainingResult, setMlTrainingResult] = useState(null);

  const [modelVersions, setModelVersions] = useState([]);
  const [modelVersionsLoading, setModelVersionsLoading] = useState(false);

  const [showDevMonitoring, setShowDevMonitoring] = useState(false);
  const [decisionStats, setDecisionStats] = useState(null);
  const [decisionStatsLoading, setDecisionStatsLoading] = useState(false);

  function notify(type, message) {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);

    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }

  function formatMetric(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    if (Number.isNaN(number)) return value;
    return `${(number * 100).toFixed(2)}%`;
  }

  function formatConfidence(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    if (Number.isNaN(number)) return value;
    return `${(number * 100).toFixed(2)}%`;
  }

  async function startFr() {
    setBasicatError("");

    try {
      const created = await createJob(basicat);
      const result = await runFrJob(created.job_id);
      setJob(result);
      notify("success", "FR lancé avec succès.");
    } catch (err) {
      if (/basicat inexistant/i.test(err.message)) {
        setBasicatError(err.message);
      }

      notify("error", `Erreur: ${err.message}`);
    }
  }

  async function processSnifEnv(envName) {
    try {
      const result = await runSnifEnvJob(job.job_id, envName);
      setJob(result);
      notify("success", `SNIF ${envName.toUpperCase()} traité avec succès.`);
    } catch (err) {
      notify("error", `Erreur: ${err.message}`);
    }
  }

  async function skipSnifEnv(envName) {
    try {
      const result = await skipSnifEnvJob(job.job_id, envName);
      setJob(result);
      notify("success", `SNIF ${envName.toUpperCase()} passé.`);
    } catch (err) {
      notify("error", `Erreur: ${err.message}`);
    }
  }

  async function finalizeMaf() {
    try {
      const result = await finalizeMafJob(job.job_id);
      setJob(result);
      notify("success", "MAF final généré avec succès.");
    } catch (err) {
      notify("error", `Erreur: ${err.message}`);
    }
  }

  async function resetAllJobs() {
    try {
      const result = await resetJobs();
      resetWorkflow();
      setJobHistory([]);
      setJobDecisionsHistory([]);
      setSelectedHistoryJobId("");
      setMlTrainingResult(null);
      notify("success", `Jobs réinitialisés (${result.cleared} effacés).`);
    } catch (err) {
      notify("error", `Erreur reset jobs: ${err.message}`);
    }
  }

  async function loadJobHistory() {
    try {
      setHistoryLoading(true);
      const data = await listJobs();
      setJobHistory(data.jobs || []);
      notify("success", "Historique des jobs chargé.");
    } catch (err) {
      notify("error", `Erreur historique: ${err.message}`);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openJobFromHistory(jobId) {
    try {
      const loadedJob = await getJob(jobId);
      setJob(loadedJob);
      setBasicat(loadedJob.basicat || "");
      setBasicatError("");
      notify("success", `Job ${loadedJob.basicat || ""} chargé.`);
    } catch (err) {
      notify("error", `Erreur chargement job: ${err.message}`);
    }
  }

  async function loadJobDecisionsHistory(jobId) {
    try {
      setDecisionsHistoryLoading(true);
      setSelectedHistoryJobId(jobId);

      const data = await getJobDecisionsHistory(jobId);
      setJobDecisionsHistory(data.decisions || []);

      notify("success", "Historique des décisions chargé.");
    } catch (err) {
      notify("error", `Erreur décisions: ${err.message}`);
    } finally {
      setDecisionsHistoryLoading(false);
    }
  }

  async function loadModelVersions() {
    try {
      setModelVersionsLoading(true);
      const data = await listModelVersions();
      setModelVersions(data.models || []);
      notify("success", "Versions ML chargées.");
    } catch (err) {
      notify("error", `Erreur versions ML: ${err.message}`);
    } finally {
      setModelVersionsLoading(false);
    }
  }

  async function loadDecisionStats() {
    try {
      setDecisionStatsLoading(true);
      const data = await getDecisionStats();
      setDecisionStats(data);
      notify("success", "Statistiques MLOps chargées.");
    } catch (err) {
      notify("error", `Erreur stats MLOps: ${err.message}`);
    } finally {
      setDecisionStatsLoading(false);
    }
  }

  async function handleTrainModel() {
    try {
      setMlTrainingLoading(true);
      const result = await trainModel();
      setMlTrainingResult(result);
      notify("success", "Modèle ML entraîné avec succès.");

      await loadModelVersions();
    } catch (err) {
      notify("error", `Erreur ML: ${err.message}`);
    } finally {
      setMlTrainingLoading(false);
    }
  }

  function toggleHistory() {
    const nextValue = !showHistory;
    setShowHistory(nextValue);

    if (nextValue && jobHistory.length === 0) {
      loadJobHistory();
    }
  }

  function toggleDevMonitoring() {
    const nextValue = !showDevMonitoring;
    setShowDevMonitoring(nextValue);

    if (nextValue) {
      if (modelVersions.length === 0) {
        loadModelVersions();
      }

      if (!decisionStats) {
        loadDecisionStats();
      }
    }
  }

  function resetWorkflow() {
    setJob(null);
    setBasicat("");
    setBasicatError("");
  }
async function finishSnifReview(envName) {
  try {
    const result = await completeSnifReview(job.job_id, envName);
    setJob(result);
    notify("success", `SNIF ${envName.toUpperCase()} terminé.`);
  } catch (err) {
    notify("error", `Erreur: ${err.message}`);
  }
}
function goToSnifStep() {
  const target = document.getElementById("snif-step-panel");

  if (target) {
    target.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } else {
    notify("success", "FR terminé. Tu peux traiter le SNIF.");
  }
}
  const envs = job?.generated_envs || [];

  const snifSequence = ["prod", "horsprod"].filter((env) =>
    envs.includes(env)
  );

  const snifStatus = job?.snif_env_status || {};

  const phaseSnifEnv =
    job?.phase && job.phase.startsWith("snif_")
      ? job.phase.replace("snif_", "")
      : null;

  const envWithHistoricalReview =
    snifSequence.find((env) =>
      (job?.historical_decisions || []).some((d) => {
        const decisionEnv = String(d.env || "").toLowerCase();
        const fromPhase = String(d.from_phase || "");
        const status = snifStatus[env];

        return (
          decisionEnv === env &&
          fromPhase === `snif_${env}` &&
          status !== "done"
        );
      })
    ) || null;

  const currentSnifEnv =
    job?.current_snif_env ||
    phaseSnifEnv ||
    envWithHistoricalReview ||
    snifSequence.find((env) => snifStatus[env] !== "done") ||
    null;

  const currentSnifStep = currentSnifEnv
    ? `${snifSequence.indexOf(currentSnifEnv) + 1}`
    : "";

  const currentSnifLabel = currentSnifEnv ? `3.${currentSnifStep}` : null;

  const pendingCount = job?.pending_decisions?.length || 0;
  const hasPendingDecisions = (job?.pending_decisions?.length || 0) > 0;

  const showSnifStep =
    !!job &&
    job.status !== "completed" &&
    (job.status === "fr_done" ||
      job.status === "snif_ready_next" ||
      job.status === "snif_complete" ||
      job.status === "waiting_decision" ||
      job.status === "historical_review" ||
      (job.phase && job.phase.startsWith("snif_")));

  const showFrDecisionTables =
    !!job &&
    (job.phase === "fr" ||
      (job?.pending_decisions || []).some((d) => d.from_phase === "fr"));
  const frPendingCount =
  !!job
    ? (job.pending_decisions || []).filter((d) => d.from_phase === "fr").length
    : 0;

const frHistoricalCount =
  !!job
    ? (job.historical_decisions || []).filter((d) => d.from_phase === "fr").length
    : 0;

const canContinueFromFrHistorical =
  !!job &&
  job.status === "fr_done" &&
  frPendingCount === 0 &&
  frHistoricalCount > 0;    

  const snifPhaseKey = currentSnifEnv ? `snif_${currentSnifEnv}` : "";

  const hasCurrentSnifPending =
    !!job &&
    !!currentSnifEnv &&
    (job.pending_decisions || []).some(
      (d) => d.env === currentSnifEnv && d.from_phase === snifPhaseKey
    );

const currentEnvHistoricalCount =
  !!job && !!currentSnifEnv
    ? (job.historical_decisions || []).filter(
        (d) => d.env === currentSnifEnv
      ).length
    : 0;

const currentEnvPendingCount =
  !!job && !!currentSnifEnv
    ? (job.pending_decisions || []).filter(
        (d) => d.env === currentSnifEnv
      ).length
    : 0;

const showSnifDecisionTable =
  !!job &&
  !!currentSnifEnv &&
  (job.phase === snifPhaseKey || job.status === "historical_review") &&
  (currentEnvPendingCount > 0 || currentEnvHistoricalCount > 0);

const canFinishSnifHistoricalReview =
  !!job &&
  !!currentSnifEnv &&
  job.status === "historical_review" &&
  currentEnvPendingCount === 0 &&
  currentEnvHistoricalCount > 0;

  const hasHistoricalReviewWaiting =
    !!job &&
    (job.historical_decisions || []).some((d) => {
      const env = String(d.env || "").toLowerCase();
      const fromPhase = String(d.from_phase || "");

      return env && fromPhase === `snif_${env}` && snifStatus[env] !== "done";
    });

  const canFinalizeMaf =
    !!job &&
    snifSequence.length > 0 &&
    snifSequence.every((env) => snifStatus[env] === "done") &&
    job.status !== "completed" &&
    job.status !== "historical_review" &&
    !hasHistoricalReviewWaiting;

  const step1Done = !!job;
  const step2Done = !!job && job.status !== "created";
  const step3Done = job?.status === "completed";

  const doneCount =
    (step1Done ? 1 : 0) + (step2Done ? 1 : 0) + (step3Done ? 1 : 0);

  const workflowProgress = `${(doneCount / 3) * 100}%`;

  const liveStatusClass = step3Done
    ? "is-success"
    : hasPendingDecisions
    ? "is-warning"
    : job
    ? "is-active"
    : "is-idle";

  return (
    <main className="app-shell">
      <div className="toast-stack">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            role="status"
            aria-live="polite"
          >
            {toast.message}
          </div>
        ))}
      </div>

      <section className={`sticky-live ${liveStatusClass}`}>
        <div className="sticky-live-left">
          <span className="live-dot" />
          <p>
            <strong>Statut live:</strong> {job?.status || "idle"}
          </p>
        </div>

        <div className="sticky-live-right">
          <p>Job: {job?.job_id ? job.job_id.slice(0, 8) : "-"}</p>
          <p>Pending: {pendingCount}</p>
          <p>Envs: {envs.length ? envs.join("/") : "-"}</p>
        </div>
      </section>

      <header className="hero">
        <p className="eyebrow">MAF Automation Studio</p>
        <h1>Industrialise tes flux FR et SNIF avec un pilotage sans friction</h1>

        <p className="hero-copy">
          Lance tes runs avec un parcours strict: génération FR, validation des
          décisions, puis génération SNIF et MAF. Chaque correction est
          réutilisée pour les prochains traitements.
        </p>

        <div className="action-row" style={{ marginTop: "1rem" }}>
          <button className="btn-secondary" onClick={resetAllJobs}>
            Réinitialiser les jobs
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={toggleHistory}
          >
            {showHistory ? "Masquer l'historique" : "Afficher l'historique"}
          </button>

          <button
            type="button"
            className="btn-secondary"
            onClick={toggleDevMonitoring}
          >
            {showDevMonitoring
              ? "Masquer Monitoring Dev / MLOps"
              : "Afficher Monitoring Dev / MLOps"}
          </button>
        </div>

        <div className="hero-kpis">
          <article>
            <p className="kpi-label">Workflow</p>
            <p className="kpi-value">3 étapes</p>
          </article>

          <article>
            <p className="kpi-label">Validation</p>
            <p className="kpi-value">FR avant SNIF</p>
          </article>

          <article>
            <p className="kpi-label">Apprentissage</p>
            <p className="kpi-value">Corrections mémorisées</p>
          </article>
        </div>
      </header>

      {showHistory && (
        <section className="panel history-panel">
          <div className="panel-head">
            <span className="step-chip">Historique</span>
            <h2>Historique des jobs</h2>
          </div>

          <div className="action-row">
            <button
              type="button"
              className="btn-secondary"
              onClick={loadJobHistory}
              disabled={historyLoading}
            >
              {historyLoading ? "Chargement..." : "Rafraîchir"}
            </button>
          </div>

          {jobHistory.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>BASICAT</th>
                    <th>Status</th>
                    <th>Phase</th>
                    <th>Mis à jour le</th>
                    <th>Action</th>
                  </tr>
                </thead>

                <tbody>
                  {jobHistory.map((item) => (
                    <tr key={item.job_id}>
                      <td>{item.basicat}</td>
                      <td>{item.status}</td>
                      <td>{item.phase}</td>
                      <td>{item.updated_at || "-"}</td>
                      <td>
                        <div className="history-actions">
                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => openJobFromHistory(item.job_id)}
                          >
                            Ouvrir
                          </button>

                          <button
                            type="button"
                            className="btn-secondary"
                            onClick={() => loadJobDecisionsHistory(item.job_id)}
                          >
                            Décisions
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="decision-empty">
              {historyLoading ? "Chargement..." : "Aucun job trouvé."}
            </p>
          )}

          {selectedHistoryJobId && (
            <div className="decisions-history-box">
              <h3>Décisions sauvegardées</h3>

              {decisionsHistoryLoading ? (
                <p className="decision-empty">Chargement des décisions...</p>
              ) : jobDecisionsHistory.length > 0 ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Env</th>
                        <th>Phase</th>
                        <th>Source IP</th>
                        <th>Destination IP</th>
                        <th>Port</th>
                        <th>Flux final</th>
                        <th>Nom final</th>
                        <th>ML</th>
                        <th>Confiance</th>
                        <th>Action</th>
                      </tr>
                    </thead>

                    <tbody>
                      {jobDecisionsHistory.map((d) => (
                        <tr key={d.decision_id}>
                          <td>{d.env || "-"}</td>
                          <td>{d.from_phase || "-"}</td>
                          <td>{d.src_ip || "-"}</td>
                          <td>{d.dst_ip || "-"}</td>
                          <td>{d.port || "-"}</td>
                          <td>{d.final_flux || "-"}</td>
                          <td>{d.final_nom || "-"}</td>
                          <td>{d.ml_modele || "-"}</td>
                          <td>
                            {d.ml_confiance
                              ? formatConfidence(d.ml_confiance)
                              : "-"}
                          </td>
                          <td>{d.action || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="decision-empty">
                  Aucune décision sauvegardée pour ce job.
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {showDevMonitoring && (
        <section className="panel dev-monitoring-panel">
          <div className="panel-head">
            <span className="step-chip">Dev / MLOps</span>
            <h2>Monitoring Dev / MLOps</h2>
          </div>

          <div className="status-banner">
            <p>
              Cette section est dédiée à l’équipe dev : suivi des modèles,
              versions ML, métriques et statistiques des décisions.
            </p>
          </div>

          <div className="action-row">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleTrainModel}
              disabled={mlTrainingLoading}
            >
              {mlTrainingLoading ? "Entraînement..." : "Entraîner le modèle"}
            </button>

            <button
              type="button"
              className="btn-secondary"
              onClick={loadModelVersions}
              disabled={modelVersionsLoading}
            >
              {modelVersionsLoading ? "Chargement..." : "Rafraîchir versions ML"}
            </button>

            <button
              type="button"
              className="btn-secondary"
              onClick={loadDecisionStats}
              disabled={decisionStatsLoading}
            >
              {decisionStatsLoading ? "Chargement..." : "Rafraîchir stats MLOps"}
            </button>
          </div>

          {mlTrainingResult && (
            <div className="status-banner">
              <p>
                <strong>Dernier entraînement:</strong> {mlTrainingResult.status}
              </p>
              <p>
                <strong>Source:</strong> {mlTrainingResult.source}
              </p>
              <p>
                <strong>Lignes utilisées:</strong>{" "}
                {mlTrainingResult.training_rows}
              </p>
              <p>
                <strong>Excel:</strong> {mlTrainingResult.excel_rows} |{" "}
                <strong>MySQL:</strong> {mlTrainingResult.mysql_rows}
              </p>
            </div>
          )}

          {decisionStats && (
            <>
              <section className="dashboard-grid">
                <article className="dashboard-card">
                  <p className="dash-label">Décisions totales</p>
                  <p className="dash-value">{decisionStats.total_decisions}</p>
                </article>

                <article className="dashboard-card">
                  <p className="dash-label">Validées</p>
                  <p className="dash-value">{decisionStats.validated_decisions}</p>
                </article>

                <article className="dashboard-card">
                  <p className="dash-label">Corrigées</p>
                  <p className="dash-value">{decisionStats.corrected_decisions}</p>
                </article>

                <article className="dashboard-card">
                  <p className="dash-label">Décisions ML</p>
                  <p className="dash-value">{decisionStats.ml_decisions}</p>
                </article>
              </section>

              <div className="status-banner">
                <p>
                  <strong>Taux acceptation ML:</strong>{" "}
                  {decisionStats.ml_acceptance_rate}%
                </p>
                <p>
                  <strong>Taux correction ML:</strong>{" "}
                  {decisionStats.ml_correction_rate}%
                </p>
                <p>
                  <strong>Confiance moyenne ML:</strong>{" "}
                  {formatConfidence(decisionStats.average_ml_confidence)}
                </p>
              </div>

              <div className="decisions-history-box">
                <h3>Répartition des flux finaux</h3>

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Flux</th>
                        <th>Nombre</th>
                      </tr>
                    </thead>

                    <tbody>
                      {Object.entries(
                        decisionStats.final_flux_distribution || {}
                      ).map(([flux, count]) => (
                        <tr key={flux}>
                          <td>{flux}</td>
                          <td>{count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {modelVersions.length > 0 && (
            <div className="decisions-history-box">
              <h3>Versions ML sauvegardées</h3>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Model ID</th>
                      <th>Rows</th>
                      <th>Excel</th>
                      <th>MySQL</th>
                      <th>Classes</th>
                      <th>Accuracy</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>F1-score</th>
                      <th>Créé le</th>
                    </tr>
                  </thead>

                  <tbody>
                    {modelVersions.map((model) => (
                      <tr key={model.model_id}>
                        <td>{model.model_id?.slice(0, 18) || "-"}</td>
                        <td>{model.training_rows ?? "-"}</td>
                        <td>{model.excel_rows ?? "-"}</td>
                        <td>{model.mysql_rows ?? "-"}</td>
                        <td>{model.n_classes ?? "-"}</td>
                        <td>{formatMetric(model.accuracy)}</td>
                        <td>{formatMetric(model.precision)}</td>
                        <td>{formatMetric(model.recall)}</td>
                        <td>{formatMetric(model.f1_score)}</td>
                        <td>{model.created_at || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="landing-grid">
        <article className="landing-card">
          <h3>Run contrôlé</h3>
          <p>Un parcours strict pilote la qualité: FR, validation puis SNIF.</p>
        </article>

        <article className="landing-card">
          <h3>Qualité tracée</h3>
          <p>
            Chaque correction est réutilisée pour améliorer les prochaines
            exécutions.
          </p>
        </article>

        <article className="landing-card">
          <h3>Exécution rapide</h3>
          <p>
            Le tableau de bord affiche en temps réel le statut, les décisions et
            les environnements détectés.
          </p>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="dashboard-card">
          <p className="dash-label">BASICAT actif</p>
          <p className="dash-value">{job?.basicat || "-"}</p>
        </article>

        <article className="dashboard-card">
          <p className="dash-label">Statut courant</p>
          <p className="dash-value">{job?.status || "idle"}</p>
        </article>

        <article className="dashboard-card">
          <p className="dash-label">Décisions en attente</p>
          <p className="dash-value">{pendingCount}</p>
        </article>

        <article className="dashboard-card">
          <p className="dash-label">Environnements</p>
          <p className="dash-value">
            {envs.length ? envs.join(" / ") : "-"}
          </p>
        </article>
      </section>

      <section className="workflow-strip">
        <div className="workflow-progress-track" aria-hidden="true">
          <span style={{ width: workflowProgress }} />
        </div>

        <article
          className={`workflow-step ${step1Done ? "is-done" : "is-active"}`}
        >
          <div className="workflow-step-head">
            <span className="workflow-icon">FR</span>
            <p>Etape 1</p>
          </div>
          <h3>Génération FR</h3>
        </article>

        <article
          className={`workflow-step ${
            step2Done ? "is-done" : step1Done ? "is-active" : ""
          }`}
        >
          <div className="workflow-step-head">
            <span className="workflow-icon">VD</span>
            <p>Etape 2</p>
          </div>
          <h3>Validation FR</h3>
        </article>

        <article
          className={`workflow-step ${
            step3Done ? "is-done" : showSnifStep ? "is-active" : ""
          }`}
        >
          <div className="workflow-step-head">
            <span className="workflow-icon">SN</span>
            <p>Etape 3</p>
          </div>
          <h3>SNIF séquencé puis MAF final</h3>
        </article>
      </section>

      <section className="info-box">
        <h2>Prérequis backend</h2>
        <p>À déposer une seule fois avant de lancer les traitements :</p>

        <div className="code-group">
          <code>backend/data/vmliste_remplie.xlsx</code>
          <code>backend/data/bdd_flux_maf.xlsx</code>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <span className="step-chip">Etape 1</span>
          <h2>Entrer BASICAT puis générer FR</h2>
        </div>

        <div className="action-row">
          {basicatError && <p className="field-error">{basicatError}</p>}

          <input
            className="basicat-input"
            placeholder="BASICAT ex: BI"
            value={basicat}
            onChange={(e) => {
              setBasicat(e.target.value.toUpperCase());
              if (basicatError) setBasicatError("");
            }}
          />

          <button onClick={startFr} disabled={!basicat}>
            Générer FR
          </button>
        </div>
      </section>

      {job && (
        <section className="panel">
          <div className="panel-head">
            <span className="step-chip">Etape 2</span>
            <h2>Finaliser FR avant SNIF</h2>
          </div>

          <div className="status-banner">
            <p>
              <strong>Status :</strong> {job.status}
            </p>
            <p>{job.message}</p>
          </div>

          {showFrDecisionTables && envs.includes("prod") && (
            <div className="env-section">
              <h3 className="env-title">PROD</h3>

              <EnvDecisionTable
                job={job}
                env="prod"
                onUpdated={setJob}
                onNotify={notify}
              />
            </div>
          )}

          {showFrDecisionTables && envs.includes("horsprod") && (
            <div className="env-section">
              <h3 className="env-title">HORSPROD</h3>

              <EnvDecisionTable
                job={job}
                env="horsprod"
                onUpdated={setJob}
                onNotify={notify}
              />
            </div>
          )}
          {canContinueFromFrHistorical && (
  <div className="completion-actions" style={{ marginTop: "18px" }}>
    <button
      type="button"
      className="btn-primary"
      onClick={goToSnifStep}
    >
      Terminer FR et passer au SNIF
    </button>
  </div>
)}
        </section>
      )}

      {showSnifStep && currentSnifEnv && (
        <section className="step-done-banner">
          Etape 2 terminée: FR est validé. Tu peux traiter le SNIF{" "}
          {currentSnifEnv.toUpperCase()}.
        </section>
      )}

      {showSnifStep && currentSnifEnv && (
         <section className="panel" id="snif-step-panel">
          <div className="panel-head">
            <span className="step-chip">Etape {currentSnifLabel}</span>
            <h2>
              Étape {currentSnifLabel} - Uploader SNIF{" "}
              {currentSnifEnv.toUpperCase()}
            </h2>
          </div>

          <p className="env-list">
            <strong>Environnement :</strong> {currentSnifEnv.toUpperCase()} - le
            fichier doit ensuite fournir les lignes à vérifier/corriger.
          </p>

          <SnifPreviewBox
            job={job}
            env={currentSnifEnv}
            onNotify={notify}
          />

          <div className="grid">
            <FileUpload
              key={currentSnifEnv}
              label={`SNIF ${currentSnifEnv.toUpperCase()}`}
              endpoint={`/jobs/${job.job_id}/upload/snif/${currentSnifEnv}`}
              onNotify={notify}
              onUploaded={async () => {
                await processSnifEnv(currentSnifEnv);
              }}
            />

            <div className="skip-snif-card">
              <h3>Passer SNIF {currentSnifEnv.toUpperCase()}</h3>

              <p>
                Utilise cette option si tu ne veux pas traiter le SNIF pour cet
                environnement.
              </p>

              <button
                type="button"
                className="btn-warning"
                onClick={() => skipSnifEnv(currentSnifEnv)}
              >
                Passer
              </button>
            </div>
          </div>

          {showSnifDecisionTable && (
            <div className="env-section">
              <EnvDecisionTable
                job={{
                  ...job,
                  pending_decisions: (job.pending_decisions || []).filter(
                    (d) =>
                      d.env === currentSnifEnv &&
                      d.from_phase === snifPhaseKey
                  ),
                }}
                env={currentSnifEnv}
                onUpdated={setJob}
                onNotify={notify}
              />
              {canFinishSnifHistoricalReview && (
  <div className="completion-actions" style={{ marginTop: "16px" }}>
    <button
      type="button"
      className="btn-primary"
      onClick={() => finishSnifReview(currentSnifEnv)}
    >
      Terminer SNIF {currentSnifEnv.toUpperCase()}
    </button>
  </div>
)}
            </div>
          )}
        </section>
      )}

      {canFinalizeMaf && (
        <section className="panel">
          <div className="panel-head">
            <span className="step-chip">Etape 4</span>
            <h2>Générer le MAF final</h2>
          </div>

          <div className="status-banner">
            <p>
              <strong>SNIF terminé :</strong> les environnements ont été traités
              séparément.
            </p>

            <p>
              Le MAF final sera créé à partir des sorties SNIF et FR déjà
              validées.
            </p>
          </div>

          <div className="completion-actions">
            <button onClick={finalizeMaf}>Générer MAF final</button>
          </div>
        </section>
      )}

      {step3Done && (
        <section className="panel completion-banner">
          <div className="completion-header">
            <h2>Traitement Fini ✓</h2>
          </div>

          <div className="completion-details">
            <article className="completion-card">
              <p className="label">BASICAT Traité</p>
              <p className="value">{job?.basicat || "-"}</p>
            </article>

            {(job?.output_path ||
              job?.files?.find((file) => /_MAF\.xlsx$/i.test(file?.path || ""))
                ?.path) && (
              <article className="completion-card">
                <p className="label">Chemin d'accès</p>
                <p className="value code">
                  {job?.output_path ||
                    job?.files?.find((file) =>
                      /_MAF\.xlsx$/i.test(file?.path || "")
                    )?.path}
                </p>
              </article>
            )}

            <article className="completion-card">
              <p className="label">Statut</p>
              <p className="value success">Completed</p>
            </article>
          </div>

          <div className="completion-actions">
            <button onClick={resetWorkflow} className="btn-primary">
              Refaire
            </button>
          </div>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);