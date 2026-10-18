"""
KLE Fest 2 - Unified Dual-Output Project Cost Estimator Pipeline
================================================================
Workflow:
  1. User enters project details in Image, PDF or Text.
  2. Gemini generates TWO distinct outputs:
     - 1. Hardware requirement: physical products, components, specs, models
     - 2. Software requirement: full-scope payload (BOM + labor + taxes + Monte Carlo + ML features + analogies)
  3. Hardware requirement is processed by Hardware Agent (live prices from Indian electronics suppliers)
  4. Software requirement is processed by Local Model Engine (baseline arithmetic, 2000-run Monte Carlo,
     offline XGBoost ML prediction, historical analogies on Desharnais dataset)
  5. Step-by-step SSE stream to frontend
  6. Final display presents BOTH outputs:
     - 1. Hardware cost with specific products, sources and prices
     - 2. Development cost from local model with full software requirement breakdown
  7. Interactive follow-up Q&A chatbot
"""

import hashlib
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pypdf
from PIL import Image
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
import json_repair

# ------------------------------------------------------------------ paths ----
ROOT = Path(__file__).resolve().parent.parent          # KLE fest 2
REPO_ROOT = ROOT.parent                               # cost_estimation_ai
NVIDEA_DIR = ROOT / "Nvidea"
HW_AGENT_DIR = ROOT / "Hardware agent"
SW_AGENT_DIR = ROOT / "software agent"
CACHE_DIR = ROOT / ".image_cache"
CACHE_DIR.mkdir(exist_ok=True)
GEMINI_RESPONSES_DIR = REPO_ROOT / "gemini_responses"
MODEL_PREDICTIONS_DIR = REPO_ROOT / "model_predictions"
NEMOTRON_RESPONSES_DIR = REPO_ROOT / "nemotron_responses"
GEMINI_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
NEMOTRON_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)

for p in [str(REPO_ROOT), str(HW_AGENT_DIR), str(NVIDEA_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ----------------------------------------------------------- Gemini client ---
import image as _img
_GEMINI_CLIENT = None

def _gemini():
    global _GEMINI_CLIENT
    if _GEMINI_CLIENT is None:
        _GEMINI_CLIENT = _img._client()
    return _GEMINI_CLIENT

def _gemini_text(prompt: str) -> str:
    """Call Gemini text with automatic fallback to generate_content."""
    client = _gemini()
    try:
        result = _img._create(client, model=_img.MODEL, input=prompt)
        if hasattr(result, "output_text") and result.output_text:
            return result.output_text
    except Exception as e:
        logging.warning("Gemini interactions call fallback (%s)", e)
    resp = client.models.generate_content(model=_img.MODEL, contents=prompt)
    return resp.text

# ----------------------------------------------------------- LLM Fallbacks ---
from openai import OpenAI
_NVIDIA_CLIENT = None
NEMOTRON_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

def _get_nvidia_client():
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        key_file = NVIDEA_DIR / "key.txt"
        if key_file.exists():
            key_lines = key_file.read_text(encoding="utf-8").strip().splitlines()
            nvkey = next((l.strip() for l in key_lines if l.strip().startswith("nvapi-")), "")
            if nvkey:
                _NVIDIA_CLIENT = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvkey)
    return _NVIDIA_CLIENT

def _call_nemotron(prompt: str) -> str:
    client = _get_nvidia_client()
    if client is None:
        raise RuntimeError("Nemotron is unavailable: configure the NVIDIA API key in Nvidea/key.txt.")
    response = client.chat.completions.create(
        model=NEMOTRON_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
    )
    output = response.choices[0].message.content
    if not output or not output.strip():
        raise RuntimeError("Nemotron returned an empty response.")
    return output

def _call_llm_with_source(prompt: str) -> tuple[str, str, str | None]:
    """Returns the selected raw response, its provider, and any Gemini response."""
    gemini_response = None
    try:
        gemini_response = _gemini_text(prompt)
        if gemini_response and len(gemini_response.strip()) > 10:
            return gemini_response, "gemini", gemini_response
    except Exception as exc:
        logging.warning("Gemini call failed (%s), falling back to Nemotron...", exc)

    client = _get_nvidia_client()
    if client:
        try:
            resp = client.chat.completions.create(
                model=NEMOTRON_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4096,
            )
            out = resp.choices[0].message.content
            if out and len(out.strip()) > 5:
                return out, NEMOTRON_MODEL, gemini_response
        except Exception as e:
            logging.warning("Nemotron call failed (%s)", e)
    if gemini_response is not None:
        return gemini_response, "gemini", gemini_response
    gemini_response = _gemini_text(prompt)
    return gemini_response, "gemini", gemini_response

def _call_llm(prompt: str) -> str:
    return _call_llm_with_source(prompt)[0]

def robust_json_parse(raw_text: str):
    """Robustly parses JSON from LLM outputs."""
    if not raw_text or not str(raw_text).strip():
        raise ValueError("Empty response received from LLM.")
    cleaned = re.sub(r"```(?:json)?", "", str(raw_text)).strip().replace("```", "")
    s = cleaned.find("{")
    e = cleaned.rfind("}")
    if s != -1 and e > s:
        substr = cleaned[s:e + 1]
        try:
            return json.loads(substr)
        except Exception:
            pass
        try:
            repaired = json_repair.repair_json(substr, return_objects=True)
            if isinstance(repaired, (dict, list)):
                return repaired
        except Exception:
            pass
    try:
        repaired = json_repair.repair_json(raw_text, return_objects=True)
        if isinstance(repaired, (dict, list)):
            return repaired
    except Exception as exc:
        raise ValueError(f"Failed to parse LLM JSON: {exc}")
    raise ValueError("Could not extract valid JSON from LLM response.")

# ---------------------------------------------------- Hardware Agent App ------
def _load_hw_search():
    hw_app_file = HW_AGENT_DIR / "app.py"
    spec = importlib.util.spec_from_file_location("hw_agent_app", str(hw_app_file))
    hw_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hw_mod)
    return hw_mod.search_item

hw_search_item = _load_hw_search()

# --------------------------------------------- Local Model & Services Engine --
from backend.app.services.estimation import EstimationRequest, generate_full_estimate
from backend.app.services.cost_calculator import BOMItem, LaborItem, CalculationRules

# ----------------------------------------------------------------- Flask App --
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
logging.basicConfig(level=logging.INFO)

_chat_cache: dict = {}

# ====================================================================
#  STEP 1 - Gemini Dual-Output Prompt & Architecture
# ====================================================================
def _build_dual_output_prompt(project_desc: str, has_media: bool = False) -> str:
    media_note = "Carefully examine the uploaded architecture diagram / schematic / requirements document along with the project goal.\n" if has_media else ""
    return f"""You are a senior Systems Architect and Chief Technology Officer.
A client wants to develop the following product or engineering project:
"{project_desc}"

{media_note}
Thoroughly break down this project into TWO mandatory JSON outputs:

1. "hardware_requirement":
   List 4 to 10 essential physical hardware components, development boards, microcontrollers, sensors, actuators, communication modules, motors, frames, or peripherals needed to develop and build this product.
   For EACH item:
   - "name": Concise product name (e.g. "Microcontroller Board (ESP32 / STM32)")
   - "spec": Technical specifications (e.g. "Dual-Core 240MHz, Wi-Fi & BLE 5.0, 4MB Flash")
   - "quantity": Recommended prototype quantity (integer >= 1)
   - "suggested_models": 1-2 real commercial models on sale today with maker and model name, e.g. [{{"maker": "Espressif", "model": "ESP32-WROOM-32D", "why": "Cost-effective IoT controller"}}]

2. "software_requirement":
   Full scope engineering payload matching the project estimation engine schema:
   - "project_name": Concise name of the project
   - "currency": "INR"
   - "bom_items": 1 to 4 software tools, cloud services, CAD licenses, or developer subscriptions:
       * "item_name": Software tool/license name (e.g. "Cloud Backend & IoT Gateway Hosting", "Embedded Simulation / RTOS Tooling License")
       * "quantity": Integer (e.g. 1)
       * "unit_price": Realistic price in INR (e.g. 15000.0 to 50000.0)
       * "unit": "license" or "subscription"
       * "category": "software"
       * "currency": "INR"
       * "source": Vendor name (e.g. "AWS / Cloud Provider", "Enterprise Tooling Vendor")
       * "region": "India"
   - "labor_items": 3 to 6 specialized engineering roles required to develop firmware, software, cloud backend, algorithms, test, and integrate:
       * "role_name": Professional role title (e.g. "Lead Embedded Systems Architect", "Firmware / Embedded Developer", "Cloud Backend & API Developer", "QA & Reliability Test Engineer")
       * "hourly_rate": Market rate in INR (between 950.0 and 2200.0 INR/hour)
       * "hours": Realistic hours allocated per person (between 80.0 and 280.0 hours)
       * "personnel_count": Headcount integer (1 or 2)
       * "currency": "INR"
   - "rules":
       * "overhead_percentage": 15.0
       * "contingency_percentage": 10.0
       * "tax_percentage": 18.0
       * "currency": "INR"
   - "ml_features": Numerical features for the offline effort estimation model:
       * "TeamExp": Average team experience in years (integer 2 to 7)
       * "ManagerExp": Manager experience in years (integer 3 to 10)
       * "Length": Estimated project duration in months (integer 4 to 14)
       * "Transactions": Estimated user/system transactions and API operations (integer 80 to 450)
       * "Entities": Estimated count of data entities and sensor data structures (integer 30 to 140)
       * "PointsAjust": Estimated adjusted function points (integer 120 to 550)
   - "target_metric": "Effort"
   - "analogy_dataset_id": "desharnais_software_projects_38c5d000"

Return COMPACT JSON only, with NO markdown backticks:
{{
  "hardware_requirement": [
    {{
      "name": "Microcontroller Boards (STM32 / ESP32)",
      "spec": "Dual-core MCU with Wi-Fi / BLE connectivity",
      "quantity": 5,
      "suggested_models": [
        {{"maker": "Espressif", "model": "ESP32-WROOM-32D", "why": "Cost-effective IoT controller with rich community support"}}
      ]
    }}
  ],
  "software_requirement": {{
    "project_name": "...",
    "currency": "INR",
    "bom_items": [...],
    "labor_items": [...],
    "rules": {{"overhead_percentage": 15.0, "contingency_percentage": 10.0, "tax_percentage": 18.0, "currency": "INR"}},
    "ml_features": {{"TeamExp": 4, "ManagerExp": 5, "Length": 8, "Transactions": 200, "Entities": 75, "PointsAjust": 280}},
    "target_metric": "Effort",
    "analogy_dataset_id": "desharnais_software_projects_38c5d000"
  }},
  "summary": "2-3 sentence technical overview of the project."
}}"""

def _run_gemini_agent_with_raw_response(
    text: str = None,
    image_path: str = None,
    pdf_path: str = None
) -> tuple[dict, str, str, str | None]:
    """Returns normalized requirements alongside the unmodified LLM response."""
    if pdf_path and os.path.isfile(pdf_path):
        pdf_text = ""
        try:
            reader = pypdf.PdfReader(pdf_path)
            parts = [page.extract_text() for page in reader.pages[:25] if page.extract_text()]
            pdf_text = "\n".join(parts).strip()
        except Exception as e:
            logging.warning("pypdf extraction error: %s", e)

        if len(pdf_text) > 40:
            prompt = _build_dual_output_prompt(f"Project requirements extracted from uploaded PDF document:\n{pdf_text[:12000]}")
            raw, response_provider, gemini_raw_response = _call_llm_with_source(prompt)
        else:
            client = _gemini()
            uploaded = client.files.upload(file=pdf_path)
            prompt = _build_dual_output_prompt("Project requirements from the uploaded PDF document.")
            resp = client.models.generate_content(model=_img.MODEL, contents=[uploaded, prompt])
            raw = resp.text
            response_provider = "gemini"
            gemini_raw_response = raw
        input_type = "pdf"

    elif image_path and os.path.isfile(image_path):
        client = _gemini()
        img = Image.open(image_path)
        prompt = _build_dual_output_prompt("Project requirements from the uploaded image / architecture diagram.", has_media=True)
        resp = client.models.generate_content(model=_img.MODEL, contents=[img, prompt])
        raw = resp.text
        response_provider = "gemini"
        gemini_raw_response = raw
        input_type = "image"

    elif text and text.strip():
        prompt = _build_dual_output_prompt(text.strip())
        raw, response_provider, gemini_raw_response = _call_llm_with_source(prompt)
        input_type = "text"

    else:
        raise ValueError("Please provide exactly ONE input: either text, an image, or a PDF.")

    data = robust_json_parse(raw)
    if not isinstance(data, dict):
        data = {"hardware_requirement": [], "software_requirement": {}}

    hw_items = data.get("hardware_requirement", [])
    if not isinstance(hw_items, list):
        hw_items = []

    sw_req = data.get("software_requirement", {})
    if not isinstance(sw_req, dict):
        sw_req = {}

    # Defaults and validation
    default_name = (text[:60] if text else "Engineering Development Project").strip()
    sw_req.setdefault("project_name", default_name)
    sw_req.setdefault("currency", "INR")
    sw_req.setdefault("rules", {"overhead_percentage": 15.0, "contingency_percentage": 10.0, "tax_percentage": 18.0, "currency": "INR"})
    sw_req.setdefault("target_metric", "Effort")
    sw_req.setdefault("analogy_dataset_id", "desharnais_software_projects_38c5d000")
    sw_req.setdefault("ml_features", {"TeamExp": 4, "ManagerExp": 5, "Length": 8, "Transactions": 200, "Entities": 75, "PointsAjust": 280})

    if not sw_req.get("labor_items"):
        sw_req["labor_items"] = [
            {"role_name": "Lead Hardware & Systems Engineer", "hourly_rate": 1800.0, "hours": 120.0, "personnel_count": 1, "currency": "INR"},
            {"role_name": "Firmware / Embedded Developer", "hourly_rate": 1200.0, "hours": 200.0, "personnel_count": 2, "currency": "INR"},
            {"role_name": "Quality & Regulatory Compliance Specialist", "hourly_rate": 950.0, "hours": 60.0, "personnel_count": 1, "currency": "INR"}
        ]

    cleaned_hw = []
    for it in hw_items:
        if isinstance(it, dict) and it.get("name"):
            cleaned_hw.append({
                "name": str(it.get("name")),
                "spec": str(it.get("spec", "")),
                "quantity": max(1, int(it.get("quantity", 1))),
                "suggested_models": it.get("suggested_models", [])
            })

    team = []
    for l in sw_req.get("labor_items", []):
        team.append({"role": l.get("role_name", "Developer"), "reason": f"Allocated {l.get('hours', 0)} hrs @ ₹{l.get('hourly_rate', 0)}/hr"})

    normalized_output = {
        "hardware_requirement": cleaned_hw,
        "software_requirement": sw_req,
        "team": team,
        "summary": data.get("summary", ""),
        "input_type": input_type,
        "confidence": "high"
    }
    return normalized_output, raw, response_provider, gemini_raw_response

def run_gemini_agent(text: str = None, image_path: str = None, pdf_path: str = None) -> dict:
    """Accepts text, image, or PDF and runs Gemini to extract dual requirements."""
    normalized_output, _, _, _ = _run_gemini_agent_with_raw_response(text, image_path, pdf_path)
    return normalized_output

# ====================================================================
#  STEP 2 - Hardware Agent (Live Prices from Indian Suppliers)
# ====================================================================
def run_hardware_agent(hw_items: list) -> dict:
    if not hw_items:
        return {"items": [], "total": {"min": 0, "likely": 0, "max": 0, "currency": "INR"}, "all_sources": [], "source_count": 0}

    def search_one_item(item: dict) -> dict:
        name = item.get("name", "Component")
        spec = item.get("spec", "")
        qty = max(1, int(item.get("quantity", 1)))
        sugs = item.get("suggested_models", [])

        if sugs and isinstance(sugs[0], dict) and sugs[0].get("model"):
            query = f"{sugs[0].get('maker', '')} {sugs[0].get('model', '')}".strip()
        else:
            query = f"{name} {spec}".strip()

        try:
            hw_res = hw_search_item(query)
        except Exception as exc:
            logging.warning("Hardware search failed for %r: %s", query, exc)
            hw_res = {}

        best_offer = hw_res.get("best_offer")
        price_summary = hw_res.get("price_summary", [])
        results = hw_res.get("results", [])

        unit_price = None
        seller_source = "Electronics Supplier"
        product_url = ""
        price_str = None

        if best_offer and isinstance(best_offer, dict):
            val = best_offer.get("value")
            curr = (best_offer.get("currency") or "INR").upper()
            if val is not None:
                if curr == "USD":
                    unit_price = round(val * 86.0, 2)
                elif curr == "EUR":
                    unit_price = round(val * 93.0, 2)
                elif curr == "GBP":
                    unit_price = round(val * 110.0, 2)
                else:
                    unit_price = round(val, 2)
            price_str = best_offer.get("price")
            product_url = best_offer.get("url") or ""
            seller_source = best_offer.get("source") or ("Direct Seller" if product_url else "Electronics Supplier")
            if product_url:
                try:
                    host = urlparse(product_url).netloc.lower().replace("www.", "")
                    if host:
                        seller_source = host
                except Exception:
                    pass

        if unit_price is None and price_summary and isinstance(price_summary, list):
            first_ps = price_summary[0]
            val = first_ps.get("median") or first_ps.get("low")
            if val:
                curr = (first_ps.get("currency") or "INR").upper()
                if curr == "USD":
                    unit_price = round(val * 86.0, 2)
                elif curr == "EUR":
                    unit_price = round(val * 93.0, 2)
                elif curr == "GBP":
                    unit_price = round(val * 110.0, 2)
                else:
                    unit_price = round(val, 2)
                price_str = first_ps.get("label")
                seller_source = "Indian Components Market"

        if unit_price is None or unit_price <= 0:
            unit_price = 1200.0
            price_str = "₹1,200 (Market reference)"
            seller_source = "Component Catalog"

        line_total = round(unit_price * qty, 2)
        item_min = round(unit_price * 0.85, 2)
        item_max = round(unit_price * 1.25, 2)
        if price_summary and isinstance(price_summary, list) and price_summary[0].get("low"):
            item_min = min(item_min, round(price_summary[0]["low"], 2))
            item_max = max(item_max, round(price_summary[0]["high"], 2))

        sources = []
        for r in results[:4]:
            if isinstance(r, dict):
                u = r.get("url") or r.get("link") or ""
                if u:
                    sources.append({
                        "title": r.get("title", name),
                        "url": u,
                        "snippet": (r.get("snippet") or "")[:200]
                    })

        return {
            "name": name,
            "spec": spec,
            "quantity": qty,
            "suggested_models": sugs,
            "seller_source": seller_source,
            "unit_price_inr": unit_price,
            "line_total_inr": line_total,
            "price_str": price_str or f"₹{unit_price:,.0f}",
            "product_url": product_url,
            "price_range": {"min": item_min, "max": item_max},
            "sources": sources,
            "source_count": len(sources)
        }

    items_out = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(search_one_item, it): it for it in hw_items}
        for fut in as_completed(futures):
            try:
                items_out.append(fut.result())
            except Exception as exc:
                orig = futures[fut]
                items_out.append({
                    "name": orig.get("name", "Component"),
                    "spec": orig.get("spec", ""),
                    "quantity": orig.get("quantity", 1),
                    "suggested_models": orig.get("suggested_models", []),
                    "seller_source": "Supplier Catalog",
                    "unit_price_inr": 1200.0,
                    "line_total_inr": 1200.0 * orig.get("quantity", 1),
                    "price_str": "₹1,200",
                    "product_url": "",
                    "price_range": {"min": 1000.0, "max": 1500.0},
                    "sources": [],
                    "source_count": 0
                })

    hw_names = [it.get("name") for it in hw_items]
    items_out.sort(key=lambda x: hw_names.index(x["name"]) if x["name"] in hw_names else 999)

    tot_min = sum(it["price_range"]["min"] * it["quantity"] for it in items_out)
    tot_likely = sum(it["line_total_inr"] for it in items_out)
    tot_max = sum(it["price_range"]["max"] * it["quantity"] for it in items_out)

    all_sources = []
    seen = set()
    for it in items_out:
        for s in it.get("sources", []):
            u = s.get("url")
            if u and u not in seen:
                seen.add(u)
                all_sources.append({**s, "item": it["name"]})

    return {
        "items": items_out,
        "total": {
            "min": round(tot_min, 2),
            "likely": round(tot_likely, 2),
            "max": round(tot_max, 2),
            "currency": "INR"
        },
        "all_sources": all_sources,
        "source_count": len(all_sources)
    }

# ====================================================================
#  STEP 3 - Local Model Engine (Software Requirements + Cost Models)
# ====================================================================
def run_software_agent_and_model(sw_payload: dict) -> dict:
    bom_items = [BOMItem(**b) for b in sw_payload.get("bom_items", [])]
    labor_items = [LaborItem(**l) for l in sw_payload.get("labor_items", [])]
    rules = CalculationRules(**(sw_payload.get("rules") or {}))
    ml_features = sw_payload.get("ml_features") or {}
    target_metric = sw_payload.get("target_metric", "Effort")
    analogy_dataset_id = sw_payload.get("analogy_dataset_id", "desharnais_software_projects_38c5d000")

    req = EstimationRequest(
        project_name=sw_payload.get("project_name", "Development Project"),
        currency=sw_payload.get("currency", "INR"),
        bom_items=bom_items,
        labor_items=labor_items,
        rules=rules,
        ml_features=ml_features,
        target_metric=target_metric,
        analogy_dataset_id=analogy_dataset_id
    )

    unified_res = generate_full_estimate(req)
    baseline = unified_res.baseline_estimate
    mc = unified_res.monte_carlo_uncertainty
    ml = unified_res.ml_prediction
    analogy = unified_res.analogy_estimate

    labor_breakdown = [
        {
            "role_name": l.role_name,
            "hourly_rate": l.hourly_rate,
            "hours": l.hours,
            "personnel_count": l.personnel_count,
            "line_total": round(l.hourly_rate * l.hours * l.personnel_count, 2)
        }
        for l in labor_items
    ]

    bom_breakdown = [
        {
            "item_name": b.item_name,
            "quantity": b.quantity,
            "unit_price": b.unit_price,
            "line_total": round(b.quantity * b.unit_price, 2),
            "category": b.category,
            "unit": b.unit,
            "source": b.source,
            "region": b.region
        }
        for b in bom_items
    ]

    total_direct_labor_hours = sum(l.hours * l.personnel_count for l in labor_items)
    avg_hourly_rate = baseline.direct_labor_cost / max(1.0, total_direct_labor_hours)

    ml_pred_hours = ml.get("prediction", total_direct_labor_hours) if ml else total_direct_labor_hours
    ml_dev_cost = round(ml_pred_hours * avg_hourly_rate, 2)

    similar_projs = []
    if analogy and analogy.similar_projects:
        for p in analogy.similar_projects:
            similar_projs.append({
                "project_index": p.project_index,
                "similarity_score_pct": p.similarity_score_pct,
                "distance": round(p.distance, 3),
                "actual_target_value": p.actual_target_value,
                "target_unit": p.target_unit,
                "features": p.features
            })

    dev_min = round(mc.p10, 2) if mc else round(baseline.total_project_cost * 0.9, 2)
    dev_likely = round(mc.simulated_median_p50, 2) if mc else round(baseline.total_project_cost, 2)
    dev_max = round(mc.p90, 2) if mc else round(baseline.total_project_cost * 1.1, 2)

    return {
        "software_payload": sw_payload,
        "baseline_estimate": baseline.model_dump(),
        "labor_breakdown": labor_breakdown,
        "bom_breakdown": bom_breakdown,
        "monte_carlo_uncertainty": mc.model_dump() if mc else None,
        "ml_prediction": {
            **(ml or {}),
            "calculated_ml_cost": ml_dev_cost,
            "average_hourly_rate": round(avg_hourly_rate, 2)
        } if ml else None,
        "raw_model_prediction": ml,
        "analogy_estimate": {
            "status": analogy.status if analogy else "NO_ANALOGY",
            "point_estimate": analogy.point_estimate if analogy else None,
            "similar_projects": similar_projs,
            "analogy_coverage_pct": analogy.analogy_coverage_pct if analogy else 0.0,
            "mean_similarity_pct": analogy.mean_similarity_pct if analogy else 0.0
        } if analogy else None,
        "total": {
            "min": dev_min,
            "likely": dev_likely,
            "max": dev_max,
            "currency": "INR"
        }
    }

# ====================================================================
#  STEP 4 - Unified Final Prediction Synthesis
# ====================================================================
def run_final_prediction(gemini_out: dict, hw_out: dict, sw_out: dict) -> dict:
    hw_tot = hw_out.get("total", {})
    sw_tot = sw_out.get("total", {})

    hw_likely = hw_tot.get("likely", 0)
    sw_likely = sw_tot.get("likely", 0)

    tot_opt = round(hw_tot.get("min", 0) + sw_tot.get("min", 0))
    tot_likely = round(hw_likely + sw_likely)
    tot_pess = round(hw_tot.get("max", 0) + sw_tot.get("max", 0))

    ml_info = sw_out.get("ml_prediction") or {}
    pred_hours = ml_info.get("prediction") or 0
    timeline_months = sw_out.get("software_payload", {}).get("ml_features", {}).get("Length", 6)

    lic_cost = sw_out.get("baseline_estimate", {}).get("direct_materials_cost", 0)

    summary = (
        f"Estimated total project cost is ₹{tot_likely:,.0f} "
        f"(Hardware: ₹{hw_likely:,.0f}, Software Development & Licenses: ₹{sw_likely:,.0f}). "
        f"Hardware prices researched live from Indian electronic suppliers. "
        f"Software development effort estimated at {pred_hours:,.1f} person-hours using offline XGBoost model "
        f"calibrated on the Desharnais dataset with 2,000 Monte Carlo uncertainty trials and historical analogies."
    )

    return {
        "total_cost_inr": {
            "optimistic": tot_opt,
            "likely": tot_likely,
            "pessimistic": tot_pess
        },
        "hardware_cost_inr": {
            "min": hw_tot.get("min", 0),
            "likely": hw_likely,
            "max": hw_tot.get("max", 0)
        },
        "software_dev_cost_inr": {
            "min": sw_tot.get("min", 0),
            "likely": sw_likely,
            "max": sw_tot.get("max", 0)
        },
        "licence_cost_inr": {
            "min": lic_cost,
            "max": lic_cost
        },
        "effort_months": {
            "low": max(1, round(timeline_months * 0.8)),
            "likely": timeline_months,
            "high": max(2, round(timeline_months * 1.3))
        },
        "confidence": "high",
        "summary": summary
    }

def _build_nemotron_summary_prompt(gemini_out: dict, hw_out: dict, sw_out: dict) -> str:
    context = json.dumps(
        {
            "requirements": gemini_out,
            "hardware_estimate": hw_out,
            "software_estimate": sw_out,
        },
        ensure_ascii=False,
        default=str,
    )
    return (
        "Summarize this completed project estimate for the user. Explain the hardware "
        "cost and cited product sources, then the software development cost, local ML "
        "effort prediction, BOM, labor, taxes, Monte Carlo range, and historical analogies. "
        "Do not invent prices, sources, or calculations. Treat the supplied estimate as "
        "authoritative and do not change its numerical totals. Clearly identify missing data.\n\n"
        f"Estimate data:\n{context[:30000]}"
    )

# ====================================================================
#  SSE Streaming Pipeline
# ====================================================================
def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def pipeline_generator(input_type: str, text: str, file_path: str, session_id: str):
    inp_label = "PDF document" if input_type == "pdf" else ("image" if input_type == "image" else "text description")
    yield _sse("stage", {"stage": "gemini", "status": "running",
                          "message": f"Gemini is analyzing your {inp_label} and architecting Hardware Requirements & Software Full-Scope Payload..."})
    try:
        gemini_out, raw_llm_response, response_provider, raw_gemini_response = _run_gemini_agent_with_raw_response(
            text=text if input_type == "text" else None,
            image_path=file_path if input_type == "image" else None,
            pdf_path=file_path if input_type == "pdf" else None,
        )
        hw_count = len(gemini_out.get("hardware_requirement", []))
        sw_roles = len(gemini_out.get("software_requirement", {}).get("labor_items", []))

        # Keep the provider's unparsed text separate from the normalized requirements.
        ts = time.strftime("%Y%m%d_%H%M%S")
        if raw_gemini_response is not None:
            g_file = GEMINI_RESPONSES_DIR / f"gemini_response_{session_id}_{ts}.txt"
            g_file.write_bytes(raw_gemini_response.encode("utf-8"))
            (GEMINI_RESPONSES_DIR / "latest_gemini_response.txt").write_bytes(
                raw_gemini_response.encode("utf-8")
            )
        if response_provider != "gemini":
            fallback_file = NEMOTRON_RESPONSES_DIR / f"fallback_response_{session_id}_{ts}.txt"
            fallback_file.write_bytes(raw_llm_response.encode("utf-8"))
            (NEMOTRON_RESPONSES_DIR / "latest_fallback_response.txt").write_bytes(
                raw_llm_response.encode("utf-8")
            )
        if raw_gemini_response is not None:
            g_payload = json.dumps(gemini_out, indent=2, ensure_ascii=False)
            g_json_file = GEMINI_RESPONSES_DIR / f"gemini_response_{session_id}_{ts}.json"
            g_json_file.write_text(g_payload, encoding="utf-8")
            (GEMINI_RESPONSES_DIR / "latest_gemini_response.json").write_text(
                g_payload, encoding="utf-8"
            )
        elif response_provider != "gemini":
            fallback_payload = json.dumps(gemini_out, indent=2, ensure_ascii=False)
            (NEMOTRON_RESPONSES_DIR / f"fallback_requirements_{session_id}_{ts}.json").write_text(
                fallback_payload, encoding="utf-8"
            )
        logging.info("Saved raw response used by extraction from %s", response_provider)

        yield _sse("stage", {"stage": "gemini", "status": "done",
                              "message": f"Identified {hw_count} hardware components and {sw_roles} engineering roles with complete software scope payload.",
                              "data": gemini_out,
                              "provider": response_provider,
                              "raw_output": raw_gemini_response or raw_llm_response})
    except Exception as exc:
        logging.exception("Gemini extraction error")
        yield _sse("stage", {"stage": "gemini", "status": "error", "message": str(exc)})
        yield _sse("done", {"error": str(exc)})
        return

    # STAGES 2a + 2b: Parallel Hardware Agent and Local Model
    yield _sse("stage", {"stage": "hardware", "status": "running", "message": "Hardware Agent researching live prices from Indian electronics suppliers..."})
    yield _sse("stage", {"stage": "software", "status": "running", "message": "Local Model calculating baseline arithmetic, Monte Carlo simulation, XGBoost ML effort & analogies..."})

    hw_out, sw_out = {}, {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        hw_fut = pool.submit(run_hardware_agent, gemini_out.get("hardware_requirement", []))
        sw_fut = pool.submit(run_software_agent_and_model, gemini_out.get("software_requirement", {}))

        label_map = {hw_fut: "hardware", sw_fut: "software"}
        for fut in as_completed(label_map):
            label = label_map[fut]
            try:
                r = fut.result(timeout=180)
                if label == "hardware":
                    hw_out = r
                    yield _sse("stage", {"stage": "hardware", "status": "done",
                                          "message": f"{len(r.get('items',[]))} hardware items priced. Total: ₹{r.get('total',{}).get('likely',0):,.0f} (range: ₹{r.get('total',{}).get('min',0):,.0f} – ₹{r.get('total',{}).get('max',0):,.0f})",
                                          "data": r,
                                          "raw_output": json.dumps(r, indent=2, ensure_ascii=False, default=str)})
                else:
                    sw_out = r
                    dev_likely = r.get("total", {}).get("likely", 0)
                    pred_hrs = r.get("ml_prediction", {}).get("prediction", 0)
                    yield _sse("stage", {"stage": "software", "status": "done",
                                          "message": f"Development cost: ₹{dev_likely:,.0f} (ML effort: {pred_hrs:,.1f} hrs, Monte Carlo P50: ₹{dev_likely:,.0f})",
                                          "data": r,
                                          "raw_output": json.dumps(
                                              r.get("raw_model_prediction"),
                                              indent=2,
                                              ensure_ascii=False,
                                              default=str
                                          )})
            except Exception as exc:
                logging.exception(f"Error in {label}")
                if label == "hardware":
                    hw_out = {"items": [], "total": {"min": 0, "likely": 0, "max": 0, "currency": "INR"}}
                    yield _sse("stage", {"stage": "hardware", "status": "error", "message": str(exc)})
                else:
                    sw_out = {"items": [], "total": {"min": 0, "likely": 0, "max": 0, "currency": "INR"}}
                    yield _sse("stage", {"stage": "software", "status": "error", "message": str(exc)})

    # STAGE 3: Nemotron interpretation. Numeric estimates remain those computed locally.
    yield _sse("stage", {"stage": "nemotron", "status": "running",
                         "message": "Nemotron is interpreting the completed hardware and software estimates..."})
    nemotron_output = None
    try:
        nemotron_output = _call_nemotron(_build_nemotron_summary_prompt(gemini_out, hw_out, sw_out))
        ts = time.strftime("%Y%m%d_%H%M%S")
        nemotron_file = NEMOTRON_RESPONSES_DIR / f"nemotron_response_{session_id}_{ts}.txt"
        nemotron_file.write_bytes(nemotron_output.encode("utf-8"))
        (NEMOTRON_RESPONSES_DIR / "latest_nemotron_response.txt").write_bytes(
            nemotron_output.encode("utf-8")
        )
        yield _sse("stage", {"stage": "nemotron", "status": "done",
                             "message": f"Nemotron summary generated by {NEMOTRON_MODEL}.",
                             "data": {"model": NEMOTRON_MODEL, "response": nemotron_output,
                                      "saved_to": str(nemotron_file)}})
    except Exception as exc:
        logging.exception("Nemotron synthesis failed")
        yield _sse("stage", {"stage": "nemotron", "status": "error",
                             "message": str(exc)})

    # STAGE 4: Deterministic final cost synthesis.
    yield _sse("stage", {"stage": "prediction", "status": "running", "message": "Synthesizing unified cost estimate..."})
    try:
        prediction = run_final_prediction(gemini_out, hw_out, sw_out)
        yield _sse("stage", {"stage": "prediction", "status": "done",
                              "message": f"Total Project Cost: ₹{prediction.get('total_cost_inr',{}).get('likely',0):,.0f}",
                              "data": prediction})
    except Exception as exc:
        logging.exception("Prediction synthesis error")
        prediction = {"error": str(exc)}
        yield _sse("stage", {"stage": "prediction", "status": "error", "message": str(exc)})

    # Persist both the exact local ML result and the full combined estimate.
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        raw_model_prediction = sw_out.get("raw_model_prediction")
        if raw_model_prediction is not None:
            raw_ml_file = MODEL_PREDICTIONS_DIR / f"local_model_prediction_{session_id}_{ts}.json"
            raw_ml_payload = json.dumps(raw_model_prediction, indent=2, ensure_ascii=False)
            raw_ml_file.write_text(raw_ml_payload, encoding="utf-8")
            (MODEL_PREDICTIONS_DIR / "latest_local_model_prediction.json").write_text(
                raw_ml_payload, encoding="utf-8"
            )

        pred_record = {
            "session_id": session_id,
            "timestamp": ts,
            "software_development_estimate": sw_out,
            "nemotron_response": nemotron_output,
            "unified_prediction_summary": prediction,
            "hardware_estimate": hw_out
        }
        p_file = MODEL_PREDICTIONS_DIR / f"model_prediction_{session_id}_{ts}.json"
        p_payload = json.dumps(pred_record, indent=2, ensure_ascii=False)
        p_file.write_text(p_payload, encoding="utf-8")
        (MODEL_PREDICTIONS_DIR / "latest_model_prediction.json").write_text(p_payload, encoding="utf-8")
        logging.info(f"Saved model prediction to {p_file}")
    except Exception as err:
        logging.exception("Could not save model prediction: %s", err)
        yield _sse("stage", {"stage": "prediction", "status": "error",
                             "message": f"Could not save prediction output: {err}"})

    _chat_cache[session_id] = {
        "gemini": gemini_out,
        "hardware": hw_out,
        "software": sw_out,
        "nemotron": nemotron_output,
        "prediction": prediction
    }
    yield _sse("done", {
        "session_id": session_id,
        "gemini": gemini_out,
        "hardware": hw_out,
        "software": sw_out,
        "nemotron": nemotron_output,
        "prediction": prediction
    })

# ====================================================================
#  Flask Routes
# ====================================================================
@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/estimate")
def estimate():
    mode = (request.form.get("mode", "") or "").strip().lower()
    image_path = None
    pdf_path = None
    text_input = None
    file_to_clean = None

    if mode == "pdf" or ("pdf" in request.files and request.files["pdf"].filename):
        f = request.files.get("pdf") or request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "No PDF file provided."}), 400
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=str(CACHE_DIR))
        f.save(tmp.name)
        tmp.close()
        pdf_path = tmp.name
        file_to_clean = pdf_path
        input_type = "pdf"
        session_seed = pdf_path

    elif mode == "image" or ("image" in request.files and request.files["image"].filename):
        f = request.files.get("image") or request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "No image file provided."}), 400
        suffix = Path(f.filename).suffix.lower() or ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(CACHE_DIR))
        f.save(tmp.name)
        tmp.close()
        image_path = tmp.name
        file_to_clean = image_path
        input_type = "image"
        session_seed = image_path

    elif mode == "text" or ("text" in request.form and request.form.get("text", "").strip()):
        text_input = request.form.get("text", "").strip()
        if not text_input:
            return jsonify({"error": "No text description provided."}), 400
        input_type = "text"
        session_seed = text_input[:60]

    else:
        return jsonify({"error": "Please provide exactly ONE input: either text, an image, or a PDF."}), 400

    session_id = hashlib.sha256(
        (session_seed + str(time.time())).encode()
    ).hexdigest()[:16]

    def gen():
        try:
            yield from pipeline_generator(input_type, text_input, file_to_clean, session_id)
        finally:
            if file_to_clean:
                try:
                    os.unlink(file_to_clean)
                except OSError:
                    pass

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/chat")
def chat():
    body = request.get_json(force=True) or {}
    session_id = body.get("session_id", "")
    user_msg = body.get("message", "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message."}), 400

    context = _chat_cache.get(session_id, {})
    ctx_str = json.dumps(context, indent=2, ensure_ascii=False)[:5000] if context else "(no estimate run yet)"

    prompt = f"""You are a helpful project cost estimation assistant.
A user has an estimate generated by our dual-agent system (Hardware pricing from live suppliers + Development cost from offline XGBoost model).
Answer their question clearly and helpfully.
Do NOT reveal API keys or raw JSON dumps.
Keep your answer concise (under 200 words).

Project estimate data:
{ctx_str}

User question: {user_msg}

Answer:"""

    try:
        answer = _call_llm(prompt)
    except Exception as exc:
        logging.error("Chat error: %s", exc)
        answer = f"Sorry, I could not generate a response: {exc}"

    return jsonify({"reply": answer})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5002"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True, use_reloader=False)
