import React, { useState } from "react";
import { askRag } from "../services/api";

export default function RagChatbot({ onNotify }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function handleAsk() {
    const cleanQuestion = question.trim();

    if (!cleanQuestion) {
      if (onNotify) onNotify("error", "Veuillez saisir une question.");
      return;
    }

    const userMessage = {
      role: "user",
      text: cleanQuestion,
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const result = await askRag(cleanQuestion);

      const assistantMessage = {
        role: "assistant",
        text: result.answer || "Aucune réponse générée.",
        model: result.model,
        source: result.source,
        routerReason: result.router_reason,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      if (onNotify) onNotify("error", `Erreur chatbot: ${err.message}`);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Erreur: ${err.message}`,
          model: "-",
          source: "error",
          routerReason: "-",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <span className="step-chip">LLM / RAG</span>
        <h2>Chatbot intelligent MAF</h2>
      </div>

      <div className="status-banner">
        <p>
          Pose une question sur les jobs, décisions, modèles ML, statistiques
          MLOps, fichiers Excel, historique ou fonctionnement du workflow.
        </p>
      </div>

      <div className="chat-box">
        {messages.length === 0 ? (
          <p className="decision-empty">
            Exemples : Quel est le modèle actif ? Combien de lignes contient la BDD flux ?
            Est-ce que GRC existe dans la VLISTE ? Explique le rôle du MLOps.
          </p>
        ) : (
          messages.map((msg, index) => (
            <div
              key={index}
              className={`chat-message ${
                msg.role === "user" ? "chat-user" : "chat-assistant"
              }`}
            >
              <strong>{msg.role === "user" ? "Vous" : "Assistant MAF"}</strong>
              <p>{msg.text}</p>

              {msg.role === "assistant" && (
                <small>
                  Modèle: {msg.model || "-"} | Source: {msg.source || "-"} | Router:{" "}
                  {msg.routerReason || "-"}
                </small>
              )}
            </div>
          ))
        )}
      </div>

      <div className="chat-input-row">
        <textarea
          value={question}
          placeholder="Pose ta question au chatbot MAF..."
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />

        <button type="button" onClick={handleAsk} disabled={loading}>
          {loading ? "Réponse..." : "Envoyer"}
        </button>
      </div>
    </section>
  );
}