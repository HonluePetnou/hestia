import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import AskRequest, AskResponse
from app.services import rag
from app.services.llm import LLMError

router = APIRouter(tags=["ask"])

# Greetings and thanks get a friendly reply instead of "insufficient data", without a search.
SMALL_TALK = re.compile(
    r"^\s*(hi|hello|hey|yo|good (morning|afternoon|evening)|thanks?( you)?|thx|merci|"
    r"bonjour|bonsoir|salut|coucou|ok(ay)?|cool|great)\s*[!.?]*\s*$",
    re.I,
)
GREETING = (
    "Hi! I'm Hestia. I answer questions about fire in space from NASA microgravity combustion "
    "research (NTRS reports, PSI investigations, NASA resources), and every answer cites its "
    "source. Try: how does flame spread change at lunar gravity? Which fuel goes out first in "
    "FLEX? What happened in the 1997 fire aboard Mir?"
)
GREETING_FR = (
    "Bonjour ! Je suis Hestia. Je réponds aux questions sur le feu dans l'espace à partir des "
    "recherches de la NASA sur la combustion en microgravité (rapports NTRS, investigations PSI, "
    "ressources NASA), en citant chaque source. Essayez : comment la flamme se propage-t-elle en "
    "gravité lunaire ? Quel carburant s'éteint en premier dans FLEX ?"
)


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, session: Session = Depends(get_session)) -> AskResponse:
    """Answer from the NASA corpus (NTRS, PSI, NASA resources) with verified citations.

    Citations read `[ID, p.X]`, or `[ID]` when the source has no page (e.g. PSI).

    `insufficient_data` is true when no indexed source supports an answer.
    """
    if m := SMALL_TALK.match(body.question):
        french = m.group(1).lower() in {"merci", "bonjour", "bonsoir", "salut", "coucou"}
        return AskResponse(
            answer=GREETING_FR if french else GREETING, citations=[], insufficient_data=False
        )
    history = [m.model_dump() for m in body.history[-6:]]
    try:
        result = rag.ask(session, body.question, history, body.sources)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AskResponse(
        answer=result.answer,
        citations=rag.build_citations(result.citations),
        insufficient_data=result.insufficient_data,
    )
