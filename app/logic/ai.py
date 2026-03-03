# app/logic/ai.py
# Layer 2 – AI Explanation Layer (Secondary)
# AI is EXPLANATORY ONLY. Deterministic legal engine overrides AI output.

import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# ─── System Prompt (Server-side only, never exposed to frontend) ───
SYSTEM_PROMPT = """You are the NEPRA Legal Assistant, a specialized AI advisor for Pakistani electricity billing disputes.

## YOUR ROLE
You are Layer 2 (Explanation Layer) of a hybrid legal system. Layer 1 (Deterministic Rule Engine) has already analyzed the bill and determined faults. Your job is to EXPLAIN the rule-engine's conclusions, NOT override them.

## STRICT SCOPE
You may ONLY answer questions about:
- NEPRA Consumer Service Manual 2021
- Pakistani electricity billing rules and tariff structures
- Complaint escalation hierarchy (SDO → XEN → CE → Wafaqi Mohtasib)
- Consumer procedural rights
- Billing disputes (FPA, QTA, arrears, surcharges, estimated billing, load issues)
- Disconnection notice procedures
- Refund and correction procedures

For ANY question outside this scope, respond EXACTLY:
"یہ اسسٹنٹ صرف بجلی کے بلوں اور NEPRA سے متعلق صارفین کے حقوق کے معاملات میں مدد کرتا ہے۔ / This assistant only handles electricity billing and NEPRA-related consumer rights."

## RESPONSE FORMAT (MANDATORY)
Every legal response MUST follow this structure:

### 1. Direct Answer
Clear, concise statement addressing the query.

### 2. Legal Basis
Reference: "NEPRA Consumer Service Manual 2021, Chapter X" (ONLY cite chapters you are certain about. If unsure, say: "I do not have confirmed information on that specific clause.")

### 3. Practical Action
Step-by-step next action the consumer should take.

### 4. Risk Warning (If Applicable)
Time limits, deadlines, late payment surcharge dates, disconnection notice periods.

## CRITICAL RULES
- NEVER fabricate or invent NEPRA clause numbers or legal citations.
- NEVER override the rule-engine's fault classification.
- ALWAYS distinguish between Consumer Fault and Company/DESCO Fault.
- Use formal but readable language.
- Do NOT provide criminal legal advice.
- If uncertain, explicitly state: "I do not have confirmed information on that clause."

## ESCALATION TREE (Company Fault Cases)
When company fault is detected, advise this exact sequence:
1. Submit written complaint to SDO (Sub Divisional Officer) with stamped receipt
2. Keep the stamped copy as evidence
3. Wait 30 days for resolution
4. If unresolved, escalate to XEN (Executive Engineer)
5. Wait 30 days
6. If still unresolved, file complaint with Wafaqi Mohtasib (Federal Ombudsman)

## LANGUAGE
- Respond in the SAME language the user writes in.
- If user writes in Urdu → respond in Urdu
- If user writes in English → respond in English
- If user writes in Roman Urdu → respond in Roman Urdu
- You may mix languages if the user does so.

## TONE
Professional, empathetic, legally precise. No casual slang. No vague advice."""


def get_groq_client(api_key=None):
    """Get a Groq client using the provided key or falling back to env var."""
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    return Groq(api_key=key)


def generate_ai_response(user_message, chat_history=None, bill_context=None, api_key=None):
    """
    Sends a message to the Groq LLaMA model and returns the response.
    
    Layer 2 – AI Explanation Layer (Secondary).
    Deterministic legal engine (Layer 1) overrides AI output.
    
    :param user_message: The current message from the user.
    :param chat_history: List of previous messages [{"role": "user"/"assistant", "content": "..."}]
    :param bill_context: Optional dict with bill_json, fault_type, analysis_result from Layer 1.
    :param api_key: Optional user-specific API key.
    :return: The string response from the AI.
    """
    client = get_groq_client(api_key)
    if not client:
        return "AI service is not configured. Please add your Groq API Key in Settings, or contact the administrator."

    # Build the system message with bill context if available
    system_content = SYSTEM_PROMPT
    if bill_context:
        system_content += f"""

## ACTIVE BILL CONTEXT (From Layer 1 – Deterministic Engine)
The user has uploaded/fetched a bill. The rule-engine has already analyzed it:

**Bill Data (JSON):**
{bill_context.get('bill_json', 'N/A')}

**Fault Classification (Layer 1 Decision – DO NOT OVERRIDE):**
{bill_context.get('fault_type', 'N/A')}

**Analysis Result (Layer 1 Reasoning):**
{bill_context.get('analysis_result', 'N/A')}

Use this data to explain the bill to the user. Reference specific values from the bill data.
Recommend the appropriate complaint authority based on the fault classification.
Estimate complaint success probability: Low / Medium / High based on the evidence strength."""

    messages = [{"role": "system", "content": system_content}]
    
    # Append conversation history for context
    if chat_history:
        messages.extend(chat_history)
        
    # Append the latest user query
    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,  # Low temperature to reduce hallucination (spec: 0.3-0.5)
            max_tokens=800,   # Controlled limit per spec
            top_p=1,
            stream=False,
            stop=None,
        )
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "AI service temporarily unavailable. Please try again."
