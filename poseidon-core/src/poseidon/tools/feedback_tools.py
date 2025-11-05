# src/tools/feedback_tools.py
from langchain_core.tools import Tool
import json

def store_feedback(args: dict) -> str:
    feedback = {
        "prompt": args.get("prompt"),
        "response": args.get("response"),
        "is_correct": args.get("is_correct"),
        "reason": args.get("reason"),
        "correct_response": args.get("correct_response")
    }
    try:
        with open("poseidon-cda/data/dpo_data/feedback_pairs.jsonl", "a") as f:
            f.write(json.dumps(feedback) + "\n")
        return json.dumps({"status": "Feedback stored"})
    except Exception as e:
        return json.dumps({"error": f"Feedback storage failed: {str(e)}"})

feedback_tool = Tool(
    name="store_feedback",
    func=store_feedback,
    description="Store user feedback for DPO tuning. Args: prompt (str), response (json), is_correct (bool), reason (str), correct_response (json)."
)
