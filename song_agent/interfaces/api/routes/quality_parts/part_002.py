from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class QualityRoutesPart002:
    def _handle_release_audio_revisions(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    sessions = self.audio_revision_store.list_sessions(release_id)
                    summary = self.audio_revision_store.gate(release_id, required=False, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "sessions": sessions, "summary": summary})
                    return
                if method == "POST":
                    session = self.audio_revision_store.create_session(release_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session, "summary": self.audio_revision_store.gate(release_id, required=False, now=_utc_now())}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/summary":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                summary = self.audio_revision_store.gate(release_id, required=False, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "summary": summary})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio revision route not found.")
                return
            session_id = parts[0]
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.audio_revision_store.read_session(release_id, session_id)
                issues = self.audio_revision_store.list_issues(release_id, session_id)
                candidates = self.audio_revision_store.list_candidates(release_id, session_id)
                closeout = self.audio_revision_store.read_closeout(release_id, session_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "session": session, "issues": issues, "candidates": candidates, "closeout": closeout})
                return
            if len(parts) == 2 and parts[1] == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_revision_store.refresh_recheck_status(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            if len(parts) == 2 and parts[1] == "close":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_revision_store.close_session(release_id, session_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            if len(parts) == 2 and parts[1] == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.audio_revision_store.archive_session(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "session": session})
                return
            if len(parts) >= 2 and parts[1] == "issues":
                if len(parts) == 2:
                    if method == "GET":
                        self._send_json({"ok": True, "release_id": release_id, "session_id": session_id, "issues": self.audio_revision_store.list_issues(release_id, session_id)})
                        return
                    if method == "POST":
                        issue = self.audio_revision_store.create_issue(release_id, session_id, self._read_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "issue": issue}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                issue_id = parts[2]
                if len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    issue = self.audio_revision_store.read_issue(release_id, session_id, issue_id)
                    self._send_json({"ok": True, "release_id": release_id, "issue": issue})
                    return
                if len(parts) == 4 and parts[3] in {"waive", "reopen"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[3] == "waive":
                        issue = self.audio_revision_store.waive_issue(release_id, session_id, issue_id, self._optional_json_body(), now=_utc_now())
                    else:
                        issue = self.audio_revision_store.reopen_issue(release_id, session_id, issue_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "issue": issue})
                    return
                if len(parts) == 5 and parts[3] == "candidates" and parts[4] == "generate":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_revision_store.generate_candidates(release_id, session_id, issue_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
            if len(parts) >= 2 and parts[1] == "candidates":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, "release_id": release_id, "session_id": session_id, "candidates": self.audio_revision_store.list_candidates(release_id, session_id)})
                    return
                candidate_id = parts[2]
                if len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    candidate = self.audio_revision_store.read_candidate(release_id, session_id, candidate_id)
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                    return
                if len(parts) == 4 and parts[3] in {"midi", "audio"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    path, media_type, filename = self.audio_revision_store.download_candidate_artifact(release_id, session_id, candidate_id, "midi" if parts[3] == "midi" else "audio")
                    self._send_file(path, media_type, filename=filename)
                    return
                if len(parts) == 4 and parts[3] in {"review", "select", "apply"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[3] == "review":
                        candidate = self.audio_revision_store.review_candidate(release_id, session_id, candidate_id, self._read_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                        return
                    if parts[3] == "select":
                        candidate = self.audio_revision_store.select_candidate(release_id, session_id, candidate_id, now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                        return
                    result = self.audio_revision_store.apply_candidate(release_id, session_id, candidate_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio revision route not found.")
        except AudioRevisionNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioRevisionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioRevisionError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (MixControlStateError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (MixControlError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_mastering(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(
                    {
                        "ok": True,
                        "release_id": release_id,
                        "summary": self.mastering_store.get_summary(release_id, now=_utc_now()),
                        "analysis": self.mastering_store.read_analysis(release_id, default={}),
                        "plan": self.mastering_store.read_plan(release_id, default={}),
                        "candidates": self.mastering_store.list_candidates(release_id),
                        "selected_candidate": self.mastering_store.read_selected_candidate(release_id, default={}),
                    }
                )
                return
            if tail == "/analyze":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                analysis = self.mastering_store.analyze(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_analyzed", {"status": analysis.get("status"), "profile_id": analysis.get("profile_id")})
                self._send_json({"ok": True, "release_id": release_id, "analysis": analysis, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                return
            if tail == "/plan":
                if method == "GET":
                    plan = self.mastering_store.read_plan(release_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.mastering_store.build_plan(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_plan_created", {"action_count": plan.get("summary", {}).get("action_count")})
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                return
            if tail == "/candidates":
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "candidates": self.mastering_store.list_candidates(release_id), "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidate = self.mastering_store.render_candidate(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_candidate_rendered", {"candidate_id": candidate.get("candidate_id"), "status": candidate.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())}, status=HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.mastering_store.refresh(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, **result})
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.mastering_store.reset(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if len(parts) >= 2 and parts[0] == "candidates":
                candidate_id = parts[1]
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    candidate = self.mastering_store.read_candidate(release_id, candidate_id)
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                    return
                if len(parts) == 5 and parts[2] == "tracks" and parts[4] == "audio":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    path = self.mastering_store.candidate_audio_path(release_id, candidate_id, parts[3])
                    self._send_file(path, "audio/wav", filename=f"{parts[3]}-mastered.wav")
                    return
                if len(parts) == 3 and parts[2] in {"review", "select"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[2] == "review":
                        candidate = self.mastering_store.review_candidate(release_id, candidate_id, self._read_json_body(), now=_utc_now())
                    else:
                        candidate = self.mastering_store.select_candidate(release_id, candidate_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Mastering route not found.")
        except MasteringNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (MasteringStateError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (MasteringQAError, MasteringProfileError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
