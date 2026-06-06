from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# =========================
# Création Job MAF
# =========================
class RunMafRequest(BaseModel):
    basicat: str


# =========================
# Décision utilisateur
# =========================
class DecisionPayload(BaseModel):
    decision_id: str
    action: str  # validate / correct / ignore

    flux: Optional[str] = None
    nom: Optional[str] = None

    # pour extension future (port, SG, etc)
    extra: Optional[Dict[str, Any]] = None


# =========================
# Etat d’un job
# =========================
class JobStatus(BaseModel):
    job_id: str
    status: str
    message: str

    pending_decisions: List[Dict[str, Any]] = []
    files: List[Dict[str, str]] = []