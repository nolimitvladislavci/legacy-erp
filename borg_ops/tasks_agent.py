"""
borg_ops/tasks_agent.py — Agentic Celery workers.

Pattern za sve agente:
  1. Ucitaj AgentTask + context fajlove
  2. Pozovi AI s tool definitions
  3. Loop: AI -> tool call -> rezultat -> AI... dok ne kaze done
  4. Na approval_needed -> status='awaiting' -> WebSocket signal Ivanu
  5. Ivan odobri/odbaci -> nastavi ili zavrsi
  6. Zapiši AgentTaskLog za svaki korak
  7. Izracunaj cost_usd
"""

import json
import logging
import time
from decimal import Decimal

from asgiref.sync import async_to_sync
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("agent_worker")

COST_PER_TOKEN = {
    "haiku":    {"in": 0.80 / 1_000_000,  "out": 4.00 / 1_000_000},
    "gemini":   {"in": 0.075 / 1_000_000, "out": 0.30 / 1_000_000},
    "deepseek": {"in": 0.27 / 1_000_000,  "out": 1.10 / 1_000_000},
    "opus":     {"in": 15.0 / 1_000_000,  "out": 75.0 / 1_000_000},
}

IVAN_PHONE = "+4915771998747"


# ── GLAVNI DISPATCHER ─────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    soft_time_limit=1800,
    max_retries=0,
    queue="heavy",
    name="borg_ops.tasks_agent.execute_agent_task",
)
def execute_agent_task(self, task_id: str):
    """Dispatcher — citaj AgentTask.agent i rouraj na pravi worker."""
    from .models import AgentTask

    try:
        task = AgentTask.objects.get(pk=task_id)
    except AgentTask.DoesNotExist:
        logger.error("AgentTask %s ne postoji", task_id)
        return

    task.status = "running"
    task.save(update_fields=["status", "updated_at"])
    _log(task, "think", "", f"Pokrecam {task.agent.upper()} agenta: {task.title}")
    _ws(task_id, {"type": "started", "agent": task.agent, "title": task.title})

    try:
        dispatch = {
            "haiku":    _run_haiku,
            "gemini":   _run_gemini,
            "deepseek": _run_deepseek,
            "opus":     _run_opus,
        }
        fn = dispatch.get(task.agent)
        if not fn:
            raise ValueError(f"Nepoznati agent: {task.agent}")
        fn(task)
    except Exception as exc:
        from .models import AgentTask as AT
        AT.objects.filter(pk=task_id).update(
            status="failed", error_log=str(exc)[:1000]
        )
        _log(task, "error", "", str(exc)[:500])
        _ws(task_id, {"type": "error", "error": str(exc)[:200]})
        logger.error("AgentTask %s failed: %s", task_id, exc)
        raise


# ── HAIKU — AGENTIC LOOP S TOOL USE ──────────────────────────────────────────

def _run_haiku(task):
    import anthropic
    from django.conf import settings
    from .agent_tools import HAIKU_TOOLS

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    system = _system_prompt("haiku", task)
    messages = [{"role": "user", "content": _user_message(task)}]
    total_in = total_out = 0
    MAX_ITER = 20

    for iteration in range(MAX_ITER):
        _ws(task.pk, {"type": "thinking", "iteration": iteration + 1,
                      "content": f"Iteracija {iteration + 1}..."})

        response = client.messages.create(
            model=settings.HAIKU_MODEL,
            max_tokens=4000,
            system=system,
            tools=HAIKU_TOOLS,
            messages=messages,
        )
        total_in  += response.usage.input_tokens
        total_out += response.usage.output_tokens

        text_parts, tool_calls = [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                if block.text.strip():
                    _log(task, "think", "", block.text[:1000])
                    _ws(task.pk, {"type": "thinking", "content": block.text[:400]})
            elif block.type == "tool_use":
                tool_calls.append(block)

        # Gotovo — nema vise tool callova
        if response.stop_reason == "end_turn" and not tool_calls:
            summary = "\n".join(text_parts)
            task.agent_summary = summary[:3000]
            task.status = "done"
            _save_cost(task, total_in, total_out, "haiku")
            task.save(update_fields=["agent_summary", "status",
                                     "tokens_in", "tokens_out", "cost_usd", "updated_at"])
            _log(task, "done", "", summary[:400])
            _ws(task.pk, {"type": "done", "summary": summary[:300],
                          "cost": str(task.cost_usd)})
            return

        # Izvrsi tool callove
        tool_results = []
        for tc in tool_calls:
            result = _execute_tool(task, tc.name, tc.input or {})
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result) if isinstance(result, dict) else str(result),
            })

            # Approval gate
            if isinstance(result, dict) and result.get("approval_needed"):
                task.status = "awaiting"
                task.requires_approval = True
                task.approval_prompt = result.get("prompt", "")
                task.agent_output = json.dumps(
                    messages[-6:] + [{"role": "assistant", "content": list(response.content)}]
                )
                _save_cost(task, total_in, total_out, "haiku")
                task.save(update_fields=[
                    "status", "requires_approval", "approval_prompt", "agent_output",
                    "tokens_in", "tokens_out", "cost_usd", "updated_at"
                ])
                _log(task, "ask_ivan", "", result.get("prompt", "")[:500], is_gate=True)
                _ws(task.pk, {
                    "type": "approval",
                    "message": result.get("prompt", ""),
                    "action": result.get("action", ""),
                    "diff_stat": result.get("diff_stat", ""),
                })
                # Notifikacija WhatsApp odmah (ne cekaj 30 min za approval gate)
                _notify_ivan_approval(task)
                return

        messages.append({"role": "assistant", "content": list(response.content)})
        messages.append({"role": "user", "content": tool_results})

    # Limit iteracija
    task.status = "failed"
    task.error_log = f"Dosegnut limit od {MAX_ITER} iteracija"
    _save_cost(task, total_in, total_out, "haiku")
    task.save(update_fields=["status", "error_log", "tokens_in", "tokens_out", "cost_usd", "updated_at"])


# ── GEMINI — RESEARCH ────────────────────────────────────────────────────────

def _run_gemini(task):
    import google.generativeai as genai
    from django.conf import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = _user_message(task)
    if task.scope == "research":
        prompt = f"[WEB RESEARCH TASK]\n{prompt}\nKoristi Google pretragu i vrati strukturirani izvjestaj."

    _ws(task.pk, {"type": "thinking", "content": "Gemini analizira..."})

    response = model.generate_content(prompt)
    text = response.text.strip()

    task.agent_summary = text[:4000]
    task.status = "done"
    meta = getattr(response, "usage_metadata", None)
    task.tokens_in  = getattr(meta, "prompt_token_count", 0)
    task.tokens_out = getattr(meta, "candidates_token_count", 0)
    task.cost_usd   = Decimal(str(
        task.tokens_in  * COST_PER_TOKEN["gemini"]["in"] +
        task.tokens_out * COST_PER_TOKEN["gemini"]["out"]
    ))
    task.save(update_fields=["agent_summary", "status",
                             "tokens_in", "tokens_out", "cost_usd", "updated_at"])
    _log(task, "done", "", text[:400])
    _ws(task.pk, {"type": "done", "summary": text[:300], "cost": str(task.cost_usd)})


# ── DEEPSEEK — CODE REVIEW / REASONING ───────────────────────────────────────

def _run_deepseek(task):
    from core.deepseek_client import deepseek_direct, deepseek_reasoner

    context = _gather_context(task)
    prompt = f"{task.instruction}\n\n{context}" if context else task.instruction

    _ws(task.pk, {"type": "thinking", "content": "DeepSeek analizira kod..."})

    if task.scope in ("write", "deploy"):
        result = deepseek_reasoner(prompt=prompt, max_tokens=2000)
    else:
        result = deepseek_direct(prompt=prompt, max_tokens=1500)

    task.agent_summary = result[:4000]
    task.status = "done"
    task.cost_usd = Decimal("0.001")
    task.save(update_fields=["agent_summary", "status", "cost_usd", "updated_at"])
    _log(task, "done", "", result[:400])
    _ws(task.pk, {"type": "done", "summary": result[:300], "cost": "~$0.001"})


# ── OPUS — ARHITEKTURALNA ANALIZA ─────────────────────────────────────────────

def _run_opus(task):
    import anthropic
    from django.conf import settings

    OPUS_MODEL = "claude-haiku-4-5-20251001"  # COST CONTROL 2026-04-17: Opus zamijenjen Haiku
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    system = (
        "Ti si Claude Opus — senior arhitekt LIMIT Connect ERP/POS sustava "
        "(Django 5.1, PostgreSQL, Celery, 83 appova, 109 firmi, HR+DE market). "
        "Dajes konkretne, strateske savjete bez floskula."
    )

    _ws(task.pk, {"type": "thinking", "content": "Opus promislja arhitekturu..."})

    response = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": task.instruction}],
    )
    text = response.content[0].text
    task.agent_summary = text[:4000]
    task.status = "done"
    _save_cost(task, response.usage.input_tokens, response.usage.output_tokens, "opus")
    task.save(update_fields=["agent_summary", "status",
                             "tokens_in", "tokens_out", "cost_usd", "updated_at"])
    _log(task, "done", "", text[:400])
    _ws(task.pk, {"type": "done", "summary": text[:300], "cost": str(task.cost_usd)})


# ── NASTAVAK NAKON ODOBRENJA ──────────────────────────────────────────────────

@shared_task(name="borg_ops.tasks_agent.continue_after_approval")
def continue_after_approval(task_id: str, approved: bool):
    """Ivan kliknuo ODOBRI ili ODBACI."""
    from .models import AgentTask
    from .agent_tools import execute_git_commit, execute_migrate

    try:
        task = AgentTask.objects.get(pk=task_id)
    except AgentTask.DoesNotExist:
        return

    if not approved:
        task.status = "rejected"
        task.requires_approval = False
        task.save(update_fields=["status", "requires_approval", "updated_at"])
        _log(task, "done", "Ivan odbacio", "ODBIJENO")
        _ws(task_id, {"type": "rejected", "message": "Ivan je odbacio akciju."})
        return

    # Izvrsi odobrenu akciju
    action = ""
    prompt = task.approval_prompt or ""
    if "git_commit" in prompt or "commit" in prompt.lower():
        action = "git_commit"
    elif "migrate" in prompt.lower():
        action = "migrate"

    if action == "git_commit":
        import re
        m = re.search(r"Commit poruka: `(.+?)`", prompt)
        commit_msg = m.group(1) if m else f"feat: {task.title}"
        result = execute_git_commit(commit_msg)
        if result["ok"]:
            task.agent_summary += f"\n\n✅ Commit: {result['commit']}"
            task.status = "done"
        else:
            task.status = "failed"
            task.error_log = result.get("error", "")

    elif action == "migrate":
        import re
        m = re.search(r"app: (\w+)", prompt)
        app = m.group(1) if m else ""
        result = execute_migrate(app)
        if result["ok"]:
            task.agent_summary += f"\n\n✅ Migracija: {result['output'][:200]}"
            task.status = "done"
        else:
            task.status = "failed"
            task.error_log = result.get("output", "")[:500]
    else:
        task.status = "done"
        task.agent_summary += "\n\n✅ Odobreno od Ivana."

    task.approved_by = task.created_by
    task.approved_at = timezone.now()
    task.requires_approval = False
    task.save(update_fields=[
        "status", "agent_summary", "error_log",
        "approved_by", "approved_at", "requires_approval", "updated_at"
    ])
    _log(task, "done", "Ivan odobrio", task.agent_summary[-200:])
    _ws(task_id, {"type": "approved", "summary": task.agent_summary[-300:]})


# ── CELERY BEAT: PROVJERA CEKAJUCIH TASKOVA ───────────────────────────────────

@shared_task(name="borg_ops.tasks_agent.check_awaiting_tasks")
def check_awaiting_tasks():
    """Svaki 15 min — ako agent ceka odobrenje > 30 min, podsjetni WhatsApp."""
    from datetime import timedelta
    from .models import AgentTask

    cutoff = timezone.now() - timedelta(minutes=30)
    pending = AgentTask.objects.filter(status="awaiting", updated_at__lt=cutoff)
    for t in pending:
        try:
            from core.whatsapp import send_text
            send_text(
                IVAN_PHONE,
                f"⏳ Agent ceka odobrenje 30+ min\n"
                f"[{t.agent.upper()}] {t.title}\n"
                f"limit-connect.com/hr/borg/fenix-soba/?task={t.pk}",
            )
        except Exception as e:
            logger.warning("WhatsApp notif failed: %s", e)
    return f"Checked {pending.count()} pending tasks"


# ── POMOCNE ───────────────────────────────────────────────────────────────────

def _execute_tool(task, tool_name: str, tool_input: dict) -> dict:
    """Pozovi tool funkciju, logiraj, WS broadcast."""
    from .agent_tools import TOOL_FUNCTION_MAP, TOOL_LOG_TYPE_MAP

    start = time.time()
    log_type = TOOL_LOG_TYPE_MAP.get(tool_name, "exec_cmd")

    _ws(task.pk, {"type": "tool_start", "tool": tool_name,
                  "input": str(tool_input)[:200]})

    fn = TOOL_FUNCTION_MAP.get(tool_name)
    if not fn:
        result = {"ok": False, "error": f"Nepoznati alat: {tool_name}"}
    else:
        try:
            result = fn(**tool_input)
        except TypeError:
            result = fn()
        except Exception as e:
            result = {"ok": False, "error": str(e)[:200]}

    elapsed = int((time.time() - start) * 1000)
    out_str = json.dumps(result)[:1000] if isinstance(result, dict) else str(result)[:500]
    _log(task, log_type, json.dumps(tool_input)[:300], out_str, elapsed)
    _ws(task.pk, {"type": "tool_end", "tool": tool_name,
                  "output": out_str[:300], "ms": elapsed})

    # Poseban diff event za write_file
    if tool_name == "write_file" and isinstance(result, dict) and result.get("diff"):
        _ws(task.pk, {
            "type": "diff",
            "path": tool_input.get("path", ""),
            "diff": result["diff"][:3000],
        })

    return result


def _system_prompt(agent: str, task) -> str:
    return (
        f"Ti si {agent.upper()} agent na LIMIT Connect ERP/POS sustavu "
        f"(Django 5.1, PostgreSQL, Celery, Redis, Nginx, 83 Django appova, "
        f"109 firmi u produkciji, HR+DE trziste, fiskalizacija FINA, GDPR).\n\n"
        f"Zadatak: {task.title}\n"
        f"Scope: {task.scope}\n\n"
        f"Obvezna pravila:\n"
        f"- Uvijek citaj models.py prije pisanja koda (nikad ne pretpostavljaj field names)\n"
        f"- Za commit koristi request_git_commit (nikad direktno git commit)\n"
        f"- manage.py check mora proci na kraju svakog zadatka\n"
        f"- Budi konkretan i direktan. Bez uvoda.\n"
        f"- Kod pisi u jednom pisanju (write_file s kompletnim sadrzajem fajla)"
    )


def _user_message(task) -> str:
    ctx = _gather_context(task)
    msg = task.instruction
    if ctx:
        msg += f"\n\n--- CONTEXT FAJLOVI ---\n{ctx}"
    return msg


def _gather_context(task) -> str:
    from .agent_tools import read_file
    parts = []
    for fpath in (task.context_files or []):
        r = read_file(fpath, max_lines=300)
        if r.get("ok"):
            parts.append(f"=== {fpath} ({r['lines']} linija) ===\n{r['content']}")
        else:
            parts.append(f"=== {fpath} === [GRESKA: {r.get('error', '?')}]")
    return "\n\n".join(parts)


def _log(task, tool_type: str, inp: str, out: str, elapsed: int = 0, is_gate: bool = False):
    from .models import AgentTaskLog
    AgentTaskLog.objects.create(
        task=task,
        tool_type=tool_type,
        tool_input=inp[:1000],
        tool_output=out[:2000],
        duration_ms=elapsed,
        is_approval_gate=is_gate,
    )


def _save_cost(task, tokens_in: int, tokens_out: int, agent: str):
    c = COST_PER_TOKEN.get(agent, COST_PER_TOKEN["haiku"])
    task.tokens_in  = tokens_in
    task.tokens_out = tokens_out
    task.cost_usd   = Decimal(str(tokens_in * c["in"] + tokens_out * c["out"]))


def _ws(task_id, data: dict):
    """Broadcast WebSocket poruku svim gledateljima ovog taska."""
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"agent_task_{task_id}",
            {"type": "agent_message", "data": data},
        )
    except Exception as e:
        logger.debug("WS send skip: %s", e)


def _notify_ivan_approval(task):
    """Odmah posalji WhatsApp kad agent trazi odobrenje."""
    try:
        from core.whatsapp import send_text
        send_text(
            IVAN_PHONE,
            f"❓ Agent ceka tvoj OK\n"
            f"[{task.agent.upper()}] {task.title}\n"
            f"{task.approval_prompt[:200]}\n"
            f"limit-connect.com/hr/borg/fenix-soba/?task={task.pk}",
        )
    except Exception:
        pass
