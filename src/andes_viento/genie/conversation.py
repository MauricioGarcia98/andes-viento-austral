"""Cliente mínimo de la Genie Conversation API (lo usan la App, el script de consola y la evaluación).

Flujo de la API:
    POST /api/2.0/genie/spaces/{space}/start-conversation        {"content": pregunta} -> conversation_id, message_id
    POST /api/2.0/genie/spaces/{space}/conversations/{c}/messages {"content": repregunta}
    GET  /api/2.0/genie/spaces/{space}/conversations/{c}/messages/{m}           -> status, attachments
    GET  .../messages/{m}/attachments/{a}/query-result                          -> filas del SQL que generó Genie

Los estados terminales son COMPLETED, FAILED y CANCELLED; mientras tanto se hace polling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "QUERY_RESULT_EXPIRED"}


@dataclass
class GenieAnswer:
    conversation_id: str
    message_id: str
    status: str
    text: str = ""
    sql: str | None = None
    description: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    error: str | None = None


class GenieClient:
    def __init__(self, workspace_client, space_id: str, timeout_s: int = 180):
        self.api = workspace_client.api_client
        self.space_id = space_id
        self.timeout_s = timeout_s

    def _base(self) -> str:
        return f"/api/2.0/genie/spaces/{self.space_id}"

    def ask(self, question: str, conversation_id: str | None = None) -> GenieAnswer:
        if conversation_id:
            msg = self.api.do("POST", f"{self._base()}/conversations/{conversation_id}/messages",
                              body={"content": question})
            conv, mid = conversation_id, msg.get("message_id") or msg.get("id")
        else:
            resp = self.api.do("POST", f"{self._base()}/start-conversation", body={"content": question})
            conv, mid = resp["conversation_id"], resp["message_id"]
        return self._wait(conv, mid)

    def _wait(self, conv: str, mid: str) -> GenieAnswer:
        deadline, delay = time.time() + self.timeout_s, 1.0
        while True:
            msg = self.api.do("GET", f"{self._base()}/conversations/{conv}/messages/{mid}")
            status = msg.get("status", "")
            if status in TERMINAL or time.time() > deadline:
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)
        ans = GenieAnswer(conv, mid, status or "TIMEOUT")
        if msg.get("error"):
            ans.error = str(msg["error"])
        for att in msg.get("attachments") or []:
            if att.get("text"):
                ans.text += att["text"].get("content", "")
            if att.get("query"):
                q = att["query"]
                ans.sql, ans.description = q.get("query"), q.get("description")
                aid = att.get("attachment_id") or att.get("id")
                try:
                    res = self.api.do("GET", f"{self._base()}/conversations/{conv}/messages/{mid}"
                                             f"/attachments/{aid}/query-result")
                    st = res.get("statement_response", {})
                    ans.columns = [c["name"] for c in st.get("manifest", {}).get("schema", {}).get("columns", [])]
                    ans.rows = st.get("result", {}).get("data_array", []) or []
                except Exception as exc:  # el resultado puede haber expirado
                    ans.error = f"query-result: {exc}"
            if att.get("suggested_questions"):
                ans.suggested_questions = att["suggested_questions"].get("questions", [])
        return ans
