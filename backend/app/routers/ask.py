from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import AskRequest, AskResponse
from app.services import rag
from app.services.llm import LLMError

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, session: Session = Depends(get_session)) -> AskResponse:
    """Answer from the NASA corpus (NTRS, PSI, NASA resources) with verified citations.

    Citations read `[ID, p.X]`, or `[ID]` when the source has no page (e.g. PSI).

    `insufficient_data` is true when no indexed source supports an answer.
    """
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
