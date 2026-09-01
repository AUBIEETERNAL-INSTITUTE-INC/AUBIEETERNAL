"""
AUBIEETERNAL — public demo (Hugging Face Space)

A lightweight, always-on demo of the AUBIEETERNAL /converse tutoring
experience that does NOT depend on the home Ryzen rig or Tailscale. It
mirrors the conversational *style* of the real product (Socratic, "name what
it hinges on", one consideration per turn, one follow-up question) but runs
on a small hosted model via the Hugging Face Inference API — it is not the
same brain, and it has no memory, no face recognition, and no progress
tracking. See the notice rendered at the top of the UI.

Config (Space -> Settings -> Variables and secrets):
  MODEL_ID   variable, optional. Default: Qwen/Qwen2.5-7B-Instruct
             (same family as the rig's qwen2.5:14b, so the tone matches).
  HF_PROVIDER variable, optional. Default: unset -> huggingface_hub picks.
             Set to "hf-inference" to force serverless HF inference.
  HF_TOKEN   secret, recommended. A read token. Spaces also inject a token
             automatically for the Space owner; this is the explicit path.
"""

import os

import gradio as gr
from huggingface_hub import InferenceClient

MODEL_ID = os.environ.get("MODEL_ID", "Qwen/Qwen2.5-7B-Instruct").strip()
HF_PROVIDER = os.environ.get("HF_PROVIDER", "").strip() or None
HF_TOKEN = (
    os.environ.get("HF_TOKEN")
    or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
)

_client_kwargs = {"api_key": HF_TOKEN}
if HF_PROVIDER:
    _client_kwargs["provider"] = HF_PROVIDER
client = InferenceClient(**_client_kwargs)

MAX_NEW_TOKENS = 400
MAX_HISTORY_TURNS = 8  # session-only; trimmed so the prompt stays small

# ── Persona ──────────────────────────────────────────────────────────────
# A trimmed, text-only adaptation of assistant_server.py's SYSTEM_PROMPT:
# the same pedagogy, minus the lines about the camera, face-ID, remembered
# people, and spoken-aloud brevity (this demo is typed and stateless).
SYSTEM_PROMPT_EN = (
    "You are Aubie, a warm, curious teacher for the AUBIEETERNAL project — a "
    "genuine conversation partner, not a Q&A machine. End each reply with "
    "exactly one thoughtful follow-up question that builds on what the person "
    "just said, unless they've signalled they're done.\n"
    "If someone asks something that has a clear right answer and they're "
    "clearly learning it (math, science, how something works), do NOT give "
    "the answer first. Offer a hint, or ask what they've already tried; give "
    "the full answer only if they're still stuck or ask you outright.\n"
    "When someone is weighing a decision or a hard question rather than "
    "looking up a fact, don't jump to an answer. First say what the choice "
    "really turns on, or ask the one clarifying question that would change "
    "your advice. Think it through with them one consideration at a time, "
    "then give your actual recommendation. Disagree kindly when you see a "
    "problem, and say why.\n"
    "Keep replies concise and conversational — the depth comes from the "
    "back-and-forth, not one long answer."
)

SYSTEM_PROMPT_ES = (
    "Eres Aubie, un maestro cálido y curioso del proyecto AUBIEETERNAL: un "
    "verdadero compañero de conversación, no una máquina de preguntas y "
    "respuestas. Termina cada respuesta con exactamente una pregunta de "
    "seguimiento que parta de lo que la persona acaba de decir, salvo que "
    "haya dejado claro que ya terminó.\n"
    "Si alguien pregunta algo que tiene una respuesta correcta clara y se ve "
    "que lo está aprendiendo (matemáticas, ciencia, cómo funciona algo), NO "
    "des la respuesta de entrada. Ofrece una pista, o pregúntale qué ha "
    "intentado ya; da la respuesta completa solo si sigue atascado o si te "
    "la pide directamente.\n"
    "Cuando alguien está sopesando una decisión o una pregunta difícil en "
    "lugar de buscar un dato, no vayas directo a la respuesta. Primero di de "
    "qué depende realmente la decisión, o haz la única pregunta aclaratoria "
    "que cambiaría tu consejo. Piénsalo con esa persona, una consideración a "
    "la vez, y luego da tu recomendación concreta. Si ves un problema, "
    "díselo con amabilidad y explica por qué.\n"
    "Mantén las respuestas breves y conversacionales: la profundidad viene "
    "del ida y vuelta, no de una sola respuesta larga. Responde SIEMPRE en "
    "español."
)

SYSTEM_PROMPTS = {"English": SYSTEM_PROMPT_EN, "Español": SYSTEM_PROMPT_ES}

ERR_EN = (
    "⚠️ The demo model is unreachable right now. If you're the maintainer: "
    "set a valid `HF_TOKEN` secret and a hosted `MODEL_ID` on the Space "
    "(Settings → Variables and secrets)."
)
ERR_ES = (
    "⚠️ El modelo del demo no está disponible en este momento. Si eres quien "
    "lo mantiene: configura un secreto `HF_TOKEN` válido y un `MODEL_ID` "
    "alojado en el Space (Ajustes → Variables y secretos)."
)

NOTICE = """\
### 🦅 AUBIEETERNAL — public demo

This is a **lightweight public demo**. The full AUBIEETERNAL system runs
**locally on donated hardware**, works **offline**, and **remembers every
lesson, question, and conversation** to build a picture of what each learner
knows. This page does none of that — it's a small hosted model showing the
teaching *style*, with no memory between sessions.

_Un demo público y ligero. El sistema completo funciona localmente, sin
conexión, y recuerda cada lección. Esta página no._
"""


def respond(message, history, language):
    system = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPT_EN)
    msgs = [{"role": "system", "content": system}]

    # history is a list of {"role", "content"} dicts (messages format, the
    # Gradio 6 default).
    for turn in history[-2 * MAX_HISTORY_TURNS :]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": message})

    try:
        out = client.chat_completion(
            messages=msgs,
            model=MODEL_ID,
            max_tokens=MAX_NEW_TOKENS,
            temperature=0.7,
        )
        return out.choices[0].message.content.strip()
    except Exception as e:  # noqa: BLE001 — surface any inference failure to the user
        print(f"[demo] inference failed: {type(e).__name__}: {e}")
        return ERR_ES if language == "Español" else ERR_EN


with gr.Blocks(title="AUBIEETERNAL — public demo") as demo:
    gr.Markdown(NOTICE)
    language = gr.Dropdown(
        choices=["English", "Español"],
        value="English",
        label="Language / Idioma",
    )
    gr.ChatInterface(
        fn=respond,
        additional_inputs=[language],
        examples=[
            ["How do I solve 2x + 4 = 10?", "English"],
            ["Should I learn Python or JavaScript first?", "English"],
            ["¿Por qué el cielo es azul?", "Español"],
            ["No sé si estudiar biología o informática. ¿Qué hago?", "Español"],
        ],
        cache_examples=False,
    )
    gr.Markdown(
        f"<sub>Demo model: <code>{MODEL_ID}</code> via Hugging Face Inference API · "
        "not affiliated with the model's authors · "
        "<a href='https://github.com/'>AUBIEETERNAL is CC0 / public domain</a></sub>"
    )

if __name__ == "__main__":
    # Gradio 6.0 moved `theme` off the Blocks/ChatInterface constructors.
    demo.launch(theme=gr.themes.Soft())
