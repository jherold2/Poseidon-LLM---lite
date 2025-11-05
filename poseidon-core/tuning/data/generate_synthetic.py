# tuning/generate_synthetic.py
import json
import random
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from poseidon.tools.query_tools_generic.query_sales_history import filter_slicers_tool
from poseidon.utils.logger_setup import setup_logging

# Initialize logging
logger = setup_logging()

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OpenAI API key not found in environment variables")
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Configuration
TASK_LIBRARY_PATH = Path("data/task_library.json")
NUM_VARIATIONS = 100
CURRENT_DATE = datetime(2025, 9, 12)  # Fixed for consistency; replace with datetime.now() for dynamic

def map_prompt_to_tools(prompt: str):
    """Map a raw prompt into a system/user/assistant JSONL entry."""
    system_msg = "<|SYSTEM|>Select tasks from [task_library.json]."
    user_msg = f"<|USER|>{prompt}"

    # Basic keyword mapping (you can expand this later)
    if "upsell" in prompt.lower():
        assistant_msg = (
            "<|ASSISTANT|>["
            "{\"tool\": \"query_customer_purchases\", \"args\": {\"customer_id\": \"<id>\", \"time_range\": \"<period>\"}}, "
            "{\"tool\": \"infer_upsell_opportunities\", \"args\": {\"purchases\": \"<output>\"}}]"
        )
    elif "forecast" in prompt.lower():
        assistant_msg = (
            "<|ASSISTANT|>["
            "{\"tool\": \"forecast_sales\", \"args\": {\"customer_id\": \"<id>\", \"time_range\": \"<period>\"}}]"
        )
    elif "order status" in prompt.lower():
        assistant_msg = (
            "<|ASSISTANT|>["
            "{\"tool\": \"check_order_status\", \"args\": {\"customer_id\": \"<id>\", \"time_range\": \"<period>\"}}]"
        )
    else:
        assistant_msg = "<|ASSISTANT|>[]"

    return {"text": f"{system_msg}{user_msg}{assistant_msg}"}


# Generate valid time ranges (last 6 months from current date)
def generate_time_ranges(current_date: datetime, months_back: int = 6) -> List[str]:
    time_ranges = []
    for i in range(months_back):
        # Calculate start date (first day of the month)
        start_date = (current_date.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        # Calculate end date (last day of the same month)
        next_month = (start_date.replace(day=28) + timedelta(days=32)).replace(day=1)
        end_date = next_month - timedelta(days=1)
        time_ranges.append(f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    return time_ranges[::-1]  # Reverse to have most recent first

VALID_TIME_RANGES = generate_time_ranges(CURRENT_DATE)

# Prompt template configuration
PROMPT_TEMPLATES = [
    {"task": "infer_upsell_opportunities", "template": "Generate upsell for {customer_id} using purchase history.", "params": ["customer_id"]},
    {"task": "infer_customer_segmentation", "template": "Segment customers for purchases from {time_range}.", "params": ["time_range"]},
    {"task": "infer_payment_risk", "template": "Analyze payment risk for {customer_id} with terms.", "params": ["customer_id"]},
    {"task": "infer_sales_forecast", "template": "Forecast sales for {customer_id} from {time_range}.", "params": ["customer_id", "time_range"]},
    {"task": "infer_delivery_risk", "template": "Evaluate delivery risk for orders from {time_range}.", "params": ["time_range"]},
    {"task": "query_customer_purchase_history", "template": "Get purchase history for {customer_id} from {time_range}.", "params": ["customer_id", "time_range"]},
    {"task": "query_sales_by_category", "template": "Show sales by category level {category_level} from {time_range}.", "params": ["category_level", "time_range"]},
    {"task": "query_order_status", "template": "Check order status for {customer_id} from {time_range}.", "params": ["customer_id", "time_range"]},
    {"task": "query_sales_metrics", "template": "Get sales metrics for {customer_id} from {time_range}.", "params": ["customer_id", "time_range"]},
    {"task": "query_product_affinities", "template": "Find product affinities for {customer_id}.", "params": ["customer_id"]},
    {"task": "query_top_performing_products", "template": "List top performing products from {time_range}.", "params": ["time_range"]},
    {"task": "query_sales_by_region", "template": "Aggregate sales by region {region} from {time_range}.", "params": ["region", "time_range"]},
    {"task": "query_salesperson_performance", "template": "Evaluate salesperson {sales_channel} performance from {time_range}.", "params": ["sales_channel", "time_range"]},
    {"task": "query_discount_trends", "template": "Analyze discount trends from {time_range}.", "params": ["time_range"]},
    {"task": "query_payment_status_summary", "template": "Summarize payment statuses from {time_range}.", "params": ["time_range"]},
]

def load_task_library() -> Dict[str, Any]:
    """Load task library from JSON file."""
    try:
        with TASK_LIBRARY_PATH.open("r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Task library file not found: {TASK_LIBRARY_PATH}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in task library: {str(e)}")
        raise

def fetch_slicer_data() -> Dict[str, Any]:
    """Fetch slicer data with validation and return default values if empty."""
    logger = setup_logging()
    print("DEBUG: Entering fetch_slicer_data")
    try:
        print("DEBUG: Invoking filter_slicers_tool")
        response = filter_slicers_tool.invoke({})
        print("DEBUG: Raw response from filter_slicers_tool:", response)
        data = json.loads(response)
        print("DEBUG: Parsed slicer data:", data)
        if "error" in data:
            logger.error(f"filter_slicers_tool returned error: {data['error']}")
            print(f"ERROR: filter_slicers_tool returned error: {data['error']}")
            print("DEBUG: Using static fallback data due to error in response")
            return {
                "customer": {
                    "customer_id": ["C100", "C101", "C102"],
                    "customer_ref": ["CR100", "CR101", "CR102"],
                    "customer": ["Customer_100", "Customer_101", "Customer_102"]
                },
                "product": {
                    "item_code": ["110006", "110007", "110008"],
                    "item_description": ["Product A", "Product B", "Product C"]
                },
                "region": {"region": ["R01", "R02", "R03"]},
                "sales_channel": {"sales_channel": ["Online", "Retail", "Direct"]},
                "category": {
                    "category_level_1": ["Electronics", "Clothing"],
                    "category_level_2": ["Gadgets", "Apparel"],
                    "category_level_3": ["Smartphones", "Shirts"]
                }
            }
        if "filter_slicers" not in data:
            logger.error("filter_slicers_tool response missing 'filter_slicers' key")
            print("ERROR: filter_slicers_tool response missing 'filter_slicers' key")
            print("DEBUG: Using static fallback data due to missing filter_slicers")
            return {
                "customer": {
                    "customer_id": ["C100", "C101", "C102"],
                    "customer_ref": ["CR100", "CR101", "CR102"],
                    "customer": ["Customer_100", "Customer_101", "Customer_102"]
                },
                "product": {
                    "item_code": ["110006", "110007", "110008"],
                    "item_description": ["Product A", "Product B", "Product C"]
                },
                "region": {"region": ["R01", "R02", "R03"]},
                "sales_channel": {"sales_channel": ["Online", "Retail", "Direct"]},
                "category": {
                    "category_level_1": ["Electronics", "Clothing"],
                    "category_level_2": ["Gadgets", "Apparel"],
                    "category_level_3": ["Smartphones", "Shirts"]
                }
            }
        print("DEBUG: Returning filter_slicers data:", data["filter_slicers"])
        return data["filter_slicers"]
    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError in filter_slicers_tool response: {str(e)}. Raw response: {response}")
        print(f"ERROR: JSONDecodeError in filter_slicers_tool response: {str(e)}. Raw response: {response}")
        print("DEBUG: Using static fallback data due to JSONDecodeError")
        return {
            "customer": {
                "customer_id": ["C100", "C101", "C102"],
                "customer_ref": ["CR100", "CR101", "CR102"],
                "customer": ["Customer_100", "Customer_101", "Customer_102"]
            },
            "product": {
                "item_code": ["110006", "110007", "110008"],
                "item_description": ["Product A", "Product B", "Product C"]
            },
            "region": {"region": ["R01", "R02", "R03"]},
            "sales_channel": {"sales_channel": ["Online", "Retail", "Direct"]},
            "category": {
                "category_level_1": ["Electronics", "Clothing"],
                "category_level_2": ["Gadgets", "Apparel"],
                "category_level_3": ["Smartphones", "Shirts"]
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch slicer data: {str(e)}")
        print(f"ERROR: Failed to fetch slicer data: {str(e)}")
        print("DEBUG: Using static fallback data due to exception")
        return {
            "customer": {
                "customer_id": ["C100", "C101", "C102"],
                "customer_ref": ["CR100", "CR101", "CR102"],
                "customer": ["Customer_100", "Customer_101", "Customer_102"]
            },
            "product": {
                "item_code": ["110006", "110007", "110008"],
                "item_description": ["Product A", "Product B", "Product C"]
            },
            "region": {"region": ["R01", "R02", "R03"]},
            "sales_channel": {"sales_channel": ["Online", "Retail", "Direct"]},
            "category": {
                "category_level_1": ["Electronics", "Clothing"],
                "category_level_2": ["Gadgets", "Apparel"],
                "category_level_3": ["Smartphones", "Shirts"]
            }
        }

def get_default_values(slicer_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Generate default values from slicer data or minimal fallbacks."""
    logger = setup_logging()
    print("DEBUG: Entering get_default_values with slicer_data:", slicer_data)

    def with_fallback(value, fallback):
        return value if value else fallback

    defaults = {
        "customer_id": with_fallback(
            slicer_data.get("customer", {}).get("customer_id", []),
            ["C100", "C101", "C102"]
        ),
        "customer_ref": with_fallback(
            slicer_data.get("customer", {}).get("customer_ref", []),
            ["CR100", "CR101", "CR102"]
        ),
        "customer": with_fallback(
            slicer_data.get("customer", {}).get("customer", []),
            ["Customer_100", "Customer_101", "Customer_102"]
        ),
        "product_code": with_fallback(
            slicer_data.get("product", {}).get("item_code", []),
            ["110006", "110007", "110008"]
        ),
        "region": with_fallback(
            slicer_data.get("region", {}).get("region", []),
            ["R01", "R02", "R03"]
        ),
        "sales_channel": with_fallback(
            slicer_data.get("sales_channel", {}).get("sales_channel", []),
            ["General Trade", "Modern Market", "Distributor"]
        ),
        "category_level": with_fallback(
            slicer_data.get("category", {}).get("category_level_1", [])
            or slicer_data.get("category", {}).get("category_level_2", [])
            or slicer_data.get("category", {}).get("category_level_3", []),
            ["Electronics", "Clothing", "Home"]
        ),
        "time_range": VALID_TIME_RANGES,
    }

    print("DEBUG: Final defaults:", defaults)
    return defaults

def generate_variations(num_variations: int = NUM_VARIATIONS) -> List[str]:
    """Generate varied prompts based on templates and slicer data."""
    slicer_data = fetch_slicer_data()
    defaults = get_default_values(slicer_data)
    variations = []

    # Mapping of parameter names to their display names
    param_display_names = {
        "customer_id": "customer id",
        "customer_ref": "customer code",
        "customer": "",
        "product_code": "product code",
        "region": "",
        "sales_channel": "",
        "category_level": "",
        "time_range": "time range"
    }
    for _ in range(num_variations):
        # Generate one set of parameter values with field names
        params = {
            "customer_id": f"{param_display_names['customer_id']} {random.choice(defaults['customer_id'])}",
            "customer_ref": f"{param_display_names['customer_ref']} {random.choice(defaults['customer_ref'])}",
            "customer": f"{param_display_names['customer']} {random.choice(defaults['customer'])}",
            "product_code": f"{param_display_names['product_code']} {random.choice(defaults['product_code'])}",
            "region": f"{param_display_names['region']} {random.choice(defaults['region'])}",
            "sales_channel": f"{param_display_names['sales_channel']} {random.choice(defaults['sales_channel'])}",
            "category_level": f"{param_display_names['category_level']} {random.choice(defaults['category_level'])}",
            "time_range": random.choice(defaults['time_range'])  # Time range doesn't need prefix
        }

        # Generate prompts for each template
        for template in PROMPT_TEMPLATES:
            try:
                prompt = template["template"].format(**{p: params[p] for p in template["params"]})
                variations.append(prompt)
            except KeyError as e:
                logger.warning(f"Failed to format prompt {template['task']}: missing parameter {str(e)}")
                continue

    logger.info(f"Generated {len(variations)} prompt variations")
    return variations

def main():
    """Main function to generate and save synthetic prompts."""
    try:
        # 1. Load prompts
        prompts_path = Path("data/synthetic_prompts.json")
        with prompts_path.open() as f:
            prompts = json.load(f)

        # 2. Map to structured dataset
        structured = [map_prompt_to_tools(p) for p in prompts]

        # 3. Save JSONL
        output_path = Path("data/sft_data/sales_insights.jsonl")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            for row in structured:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(structured)} training samples to {output_path}")

    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()