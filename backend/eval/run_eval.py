"""
Runs the golden set against a live deployment of the API and checks each
answer for expected signal. This is deliberately simple (keyword
presence, not semantic scoring) -- the point isn't a perfect eval, it's
having *any* automated regression check that runs on every deploy, which
is the piece a from-scratch training project has no reason to include.

Run with:   python eval/run_eval.py --url http://localhost:8000
Exit code:  0 if all checks pass, 1 if any fail (so CI can gate on it).
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"

REFUSAL_PHRASES = [
    "don't have", "do not have", "can't answer", "cannot answer",
    "not in", "contact masa member services", "doesn't contain",
    "not sure", "unable to find",
]


def check_case(case: dict, answer: str) -> tuple[bool, str]:
    answer_lower = answer.lower()

    if case.get("expect_refusal"):
        if any(p in answer_lower for p in REFUSAL_PHRASES):
            return True, "correctly declined off-topic/unanswerable question"
        return False, "expected a refusal/declined answer, model answered anyway"

    keywords = [k.lower() for k in case.get("expect_keywords_any", [])]
    if keywords and not any(k in answer_lower for k in keywords):
        return False, f"none of expected keywords found: {keywords}"

    return True, "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the running API")
    args = parser.parse_args()

    cases = json.loads(GOLDEN_SET_PATH.read_text())
    failures = []

    with httpx.Client(timeout=30.0) as client:
        for i, case in enumerate(cases, 1):
            resp = client.post(f"{args.url}/ask", json={"query": case["query"]})
            resp.raise_for_status()
            answer = resp.json()["answer"]

            passed, reason = check_case(case, answer)
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] ({i}/{len(cases)}) {case['query']}")
            if not passed:
                print(f"         reason: {reason}")
                print(f"         answer: {answer[:200]}")
                failures.append(case["query"])

    print(f"\n{len(cases) - len(failures)}/{len(cases)} passed.")
    if failures:
        print("Failed cases:")
        for q in failures:
            print(f"  - {q}")
        sys.exit(1)


if __name__ == "__main__":
    main()
