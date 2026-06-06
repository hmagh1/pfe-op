import React, { useState } from "react";
import { askRag } from "../services/api";

export default function RagChatbot({ onNotify }) {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Bonjour, je suis l’assistant MAF. Je peux répondre sur les jobs, décisions, modèles ML, MLOps, fichiers Excel, VLISTE, BDD flux et workflow.",
      model: "system",
      source: "welcome",
      routerReason: "-",
    },
  ]);
  const [loading, setLoading] = useState(false);

  async function handleAsk() {
    const cleanQuestion = question.trim();

    if (!cleanQuestion) {
      if (onNotify) onNotify("error", "Veuillez saisir une question.");
      return;
    }

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        text: cleanQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const result = await askRag(cleanQuestion);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: result.answer || "Aucune réponse générée.",
          model: result.model,
          source: result.source,
          routerReason: result.router_reason,
        },
      ]);
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

  function askSuggestion(text) {
    setQuestion(text);
  }

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          className="rag-floating-button"
          onClick={() => setIsOpen(true)}
        >
          <span className="rag-floating-icon">AI</span>
          <span className="rag-floating-text">Assistant MAF</span>
        </button>
      )}

      {isOpen && (
        <div className="rag-popup">
          <div className="rag-popup-header">
            <div>
              <p className="rag-popup-eyebrow">LLM / RAG</p>
              <h3>Assistant intelligent MAF</h3>
            </div>

            <button
              type="button"
              className="rag-close-button"
              onClick={() => setIsOpen(false)}
            >
              ×
            </button>
          </div>

          <div className="rag-popup-description">
            Pose une question sur les jobs, décisions, modèles ML, statistiques
            MLOps, fichiers Excel, VLISTE, BDD flux ou workflow.
          </div>

          <div className="rag-suggestions">
            <button
              type="button"
              onClick={() => askSuggestion("Quel est le modèle actif ?")}
            >
              Modèle actif
            </button>

            <button
              type="button"
              onClick={() =>
                askSuggestion("Combien de lignes contient la BDD flux ?")
              }
            >
              BDD flux
            </button>

            <button
              type="button"
              onClick={() =>
                askSuggestion("Explique le rôle du MLOps dans ce projet.")
              }
            >
              MLOps
            </button>
          </div>

          <div className="rag-chat-window">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`rag-message ${
                  msg.role === "user" ? "rag-message-user" : "rag-message-bot"
                }`}
              >
                <div className="rag-message-author">
                  {msg.role === "user" ? "Vous" : "Assistant MAF"}
                </div>

                <div className="rag-message-text">{msg.text}</div>

                {msg.role === "assistant" && (
                  <div className="rag-message-meta">
                    Modèle: {msg.model || "-"} | Source: {msg.source || "-"} |
                    Router: {msg.routerReason || "-"}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="rag-message rag-message-bot">
                <div className="rag-message-author">Assistant MAF</div>
                <div className="rag-typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <div className="rag-input-area">
            <textarea
              value={question}
              placeholder="Pose ta question..."
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />

            <button type="button" onClick={handleAsk} disabled={loading}>
              {loading ? "..." : "Envoyer"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}