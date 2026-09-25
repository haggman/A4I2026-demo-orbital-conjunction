"""Time the candidate Gemini models right now, before a session, and say which to use.

    python agent/model_check.py                        # A4I_MODEL plus A4I_MODEL_CANDIDATES, from demo.env
    python agent/model_check.py MODEL_ID [MODEL_ID...] # any models you name (A4I_MODEL is always included)
    python agent/model_check.py --tier priority        # try the Priority PayGo tier as well as standard
    python agent/model_check.py --tries 5 --small      # more tries; a short prompt instead of an agent-sized one

Why: on 2026-09-25 Gemini 3.8 Flash answered the same request in 2 s, then 30 s, then 42 s. The agent copes
(time limits, retries, backoff), but a slow model is dead air on a stage. Each call here is the size of one
of the agent's real steps (about 20,000 tokens in, a short answer out), with the thinking level from demo.env.
Busy answers (429, 5xx) are retried with exponential backoff, and counted.
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cymbal_ops import config  # noqa: E402  (reads demo.env)

from google import genai  # noqa: E402
from google.genai import errors, types  # noqa: E402

QUESTION = "In one sentence: what is a conjunction assessment? Do not call any tools."
PADDING = "Reference material follows; it is not needed for the answer. " + \
          "Orbital debris is tracked by radar and published as mean elements. " * 1800   # ~20k tokens


def one_call(client, model, cfg, text, timeout_s):
    t = time.perf_counter()
    try:
        r = client.models.generate_content(model=model, contents=text, config=cfg)
        um = r.usage_metadata
        return {"s": time.perf_counter() - t, "ok": bool(r.text), "in": um.prompt_token_count if um else None}
    except errors.APIError as e:
        return {"s": time.perf_counter() - t, "ok": False, "error": f"{e.code} {str(e.message or e)[:90]}"}
    except Exception as e:                                          # timeouts and the like
        return {"s": time.perf_counter() - t, "ok": False, "error": f"{type(e).__name__}: {str(e)[:90]}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--tier", default=None, help="also try this service tier, e.g. priority")
    ap.add_argument("--small", action="store_true", help="a short prompt instead of an agent-sized one")
    ap.add_argument("--timeout", type=float, default=120.0, help="seconds before one call is given up")
    a = ap.parse_args()

    models = list(dict.fromkeys([config.MODEL] + (a.models or config.MODEL_CANDIDATES)))
    tiers = list(dict.fromkeys([config.SERVICE_TIER, (a.tier or "").lower()])) if a.tier else [config.SERVICE_TIER]
    text = QUESTION if a.small else PADDING + "\n\n" + QUESTION
    retry = types.HttpRetryOptions(attempts=4, initial_delay=config.BACKOFF_FIRST_S, max_delay=config.BACKOFF_MAX_S,
                                   exp_base=2.0)
    client = genai.Client(vertexai=True, project=config.PROJECT, location=config.MODEL_LOCATION,
                          http_options=types.HttpOptions(retry_options=retry, timeout=int(a.timeout * 1000)))

    print(f"Project {config.PROJECT} · location {config.MODEL_LOCATION} · thinking "
          f"{config.THINKING_LEVEL or '(not sent)'} · {a.tries} tries each · "
          f"{'short' if a.small else 'agent-sized (~20k tokens)'} prompt\n")
    rows, original_tier = [], config.SERVICE_TIER
    for model in models:
        for tier in tiers:
            config.SERVICE_TIER = tier
            cfg = config.generate_config(max_output_tokens=200)
            label = f"{model} [{tier or 'standard'}]"
            results = []
            for i in range(a.tries):
                res = one_call(client, model, cfg, text, a.timeout)
                results.append(res)
                print(f"  {label:44} try {i + 1}: {res['s']:5.1f}s  "
                      + ("ok" if res["ok"] else res.get("error", "empty reply")), flush=True)
                if not res["ok"] and res.get("error", "").startswith(("400", "404", "403")):
                    break                                       # the model or setting is not available: stop
            config.SERVICE_TIER = original_tier
            good = [r["s"] for r in results if r["ok"]]
            rows.append((label, model, tier, good, len(results) - len(good)))

    print("\n  model [tier]                                  fastest  median  slowest  failed")
    for label, _, _, good, bad in rows:
        if good:
            print(f"  {label:44} {min(good):6.1f}s {statistics.median(good):6.1f}s {max(good):7.1f}s  {bad:>5}")
        else:
            print(f"  {label:44}      —       —        —   {bad:>5}")
    usable = [r for r in rows if r[3] and r[4] == 0] or [r for r in rows if r[3]]
    if not usable:
        print("\nNothing answered. Check the model IDs, the project's Vertex AI access, and try again in a minute.")
        sys.exit(1)
    best = min(usable, key=lambda r: statistics.median(r[3]))
    current = [r for r in usable if r[1] == config.MODEL and r[2] == config.SERVICE_TIER]
    if current and statistics.median(current[0][3]) <= 1.2 * statistics.median(best[3]) + 1.0:
        best = current[0]                      # close enough: do not switch models for a second
    print(f"\nFastest right now: {best[0]}, median {statistics.median(best[3]):.1f}s.")
    if best[1] != config.MODEL or best[2] != config.SERVICE_TIER:
        print("To use it, set these in demo.env, then restart adk web (or redeploy):")
        print(f"  A4I_MODEL={best[1]}")
        if best[2] != config.SERVICE_TIER:
            print(f"  A4I_SERVICE_TIER={best[2]}")
    else:
        print("That is what demo.env already uses.")


if __name__ == "__main__":
    main()
