from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.mock_data import MOCK_DOCUMENTS, mock_doc_url
from app.schemas import AskRequest, AskResponse, Citation
from app.services import retrieval
from app.services.llm import LLMError, get_provider

router = APIRouter(tags=["ask"])

SYSTEM_PROMPT = (
    "You answer questions about NASA microgravity combustion research. "
    "Use ONLY the provided sources and cite them as [NTRS-ID, p.X]. "
    "If the sources do not contain the answer, say so."
)


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, session: Session = Depends(get_session)) -> AskResponse:
    """Phase 1: wiring only. Retrieval is a stub, so mock citations are returned."""
    chunks = retrieval.search(session, body.question)
    try:
        answer = get_provider().complete(
            SYSTEM_PROMPT, [{"role": "user", "content": body.question}]
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if chunks:
        citations = [
            Citation(ntrs_id=c.ntrs_id, title=c.title, page=c.page, url=c.url) for c in chunks
        ]
    else:  # TODO(hackathon): return insufficient_data=True once retrieval is real
        doc = MOCK_DOCUMENTS[0]
        citations = [
            Citation(
                ntrs_id=doc["ntrs_id"], title=doc["title"], page=4, url=mock_doc_url(doc["ntrs_id"])
            )
        ]
    return AskResponse(answer=answer, citations=citations, insufficient_data=False)
