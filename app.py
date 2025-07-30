import streamlit as st
from typing import Optional, TypedDict
import os
from groq import Groq
from langgraph.graph import StateGraph, END

class ProspectMessageState(TypedDict):
    prospect_name: Optional[str]
    designation: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    prospect_background: str
    my_background: str
    web_summary: Optional[str]
    event_name: Optional[str]
    event_details: Optional[str]
    final_message: Optional[str]

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]    

client = Groq(api_key=GROQ_API_KEY)

def groq_llm(prompt: str, model: str = "llama3-8b-8192", temperature: float = 0.3) -> str:
    """Generate text using Groq API"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()

def summarizer(text: str) -> str:
    """Summarize long backgrounds into key points"""
    if not text or not isinstance(text, str):
        return "No content to summarize."

    truncated_text = text[:4000]
    prompt = f"""
Create 3 concise bullet points from this background text. Focus on key professional highlights and achievements:

{truncated_text}

Bullet points:
-"""
    try:
        return groq_llm(prompt).strip()
    except Exception as e:
        print(f"Summarization error: {e}")
        return "Background summary unavailable"



def summarize_backgrounds(state: ProspectMessageState) -> ProspectMessageState:
    """Node to summarize prospect and user backgrounds"""
    return {
        **state,
        "prospect_background": summarizer(state["prospect_background"]),
        "my_background": summarizer(state["my_background"])
    }

import re

def extract_name_from_background(background: str) -> str:
    if not background:
        return "there"
    # Take first two capitalized words as name
    match = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?', background)
    if match:
        return match[0]
    return "there"
def generate_message(state: ProspectMessageState) -> ProspectMessageState:
    """Node to generate LinkedIn message with event context"""
    prospect_first_name = extract_name_from_background(state['prospect_background'])
    my_name = "Sumana"  # Hardcoded for consistency

    prompt = f"""
     IMPORTANT: Output ONLY the message itself. 
Do NOT include any explanations, labels, or introductions.
Create a SHORT LinkedIn connection message (MAX 3 LINES) following this natural pattern:

1. "Hi {prospect_first_name},"
2. Mention company participation in event: "I see that you will be attending {state.get('event_name', '')}"
3. Highlight one specific achievement/role from their background WITHOUT using flattery words (avoid:  exploring,  interested,  learning, No easy feat, Impressive, Noteworthy, Remarkable, Fascinating, Admiring, Inspiring, No small feat, No easy task, Stood out)
4. Avoid these kind of flattery words  exploring,  interested,  learning, No easy feat, Impressive, Noteworthy, Remarkable, Fascinating, Admiring, Inspiring, No small feat, No easy task, Stood out
5. Express your attendance and desire to connect
6. Close with "Best, {my_name}"


Examples:

Hi Tamara,
I see that you’ll be attending Ai4 Vegas 2025. Your leadership in driving agentic AI, multi-agent systems, AI governance to transform healthcare and enterprise outcomes really caught my attention. I’ll be there too & looking forward to catching up with you at the event!
Best,
{my_name}

Hi Arthy,
I see you’ll be attending Ai4 Vegas 2025. Your leadership in driving business transformation, especially in AI adoption and literacy, really caught my attention. I’ll be there too and would love to connect at the event!

Best,
{my_name}

Hi Harveer,
I see that you’ll be attending  Ai4 Vegas 2025. Your leadership in scaling enterprise AI and driving data-led digital transformation in banking and telecom really caught my attention. I’ll be there too & looking forward to catching up with you at the event.
Best,
{my_name}


Now create for:
Prospect: {state['prospect_name']} ({state['designation']} at {state['company']})
Key Highlight: {state['prospect_background']}
Event: {state.get('event_name', '')}

Message (MAX 2-3 LINES within 250 chars - follow the pattern above):
Hi {prospect_first_name},"""

    try:
        response = groq_llm(prompt, temperature=0.7)
        # Clean response
        message = response.strip()
        unwanted_starts = [
            "Here is a LinkedIn connection message",
            "Here’s a LinkedIn message",
            "LinkedIn connection message:",
            "Message:",
            "Output:"
        ]
        for phrase in unwanted_starts:
            if message.lower().startswith(phrase.lower()):
                message = message.split("\n", 1)[-1].strip()

        # Ensure connection note is present
        connection_phrases = ["look forward", "would be great", "hope to connect", "love to connect", "looking forward"]
        if not any(phrase in message.lower() for phrase in connection_phrases):
            # Add connection note if missing
            message += "\nI'll be there too & looking forward to catching up with you at the event."

        if state['company'].lower() not in message.lower():
            # Add company mention if missing
            message = message.replace(
                f"Hi {prospect_first_name},",
                f"Hi {prospect_first_name},\nI see that you will be attending  {state.get('event_name', '')}.",
                1
            )

            
        if message.count(f"Best, {my_name}") > 1:
            parts = message.split(f"Best, {my_name}")
            message = parts[0].strip() + f"\n\nBest, {my_name}"

        return {**state, "final_message": message}
    except Exception as e:
        print(f"Message generation failed: {e}")
        return {**state, "final_message": "Failed to generate message"}
# =====================
# Build LangGraph Workflow
# =====================
workflow = StateGraph(ProspectMessageState)
workflow.add_node("summarize_backgrounds", summarize_backgrounds)
workflow.add_node("generate_message", generate_message)
workflow.set_entry_point("summarize_backgrounds")
workflow.add_edge("summarize_backgrounds", "generate_message")
workflow.add_edge("generate_message", END)
graph1 = workflow.compile()

# =====================
# Streamlit UI
# =====================
st.set_page_config(page_title="LinkedIn Message Generator", layout="centered")
st.title(" First Level Msgs for Ai4 Vegas 2025")

with st.form("prospect_form"):
    # prospect_name = st.text_input("Prospect Name", "Brent Parks")
    # designation = st.text_input("Designation", "")
    # company = st.text_input("Company", "")
    # industry = st.text_input("Industry", "")
    prospect_background = st.text_area("Prospect Background", "Prospect professional background goes here...")
    my_background = st.text_area("Your Background", "Your professional background goes here...")
    event_name = st.text_input("Event Name", "Ai4 Vegas 2025")
    event_details = st.text_input("Event Details", "August 12-14, MGM Grand Las Vegas")

    submitted = st.form_submit_button("Generate Message")

if submitted:
    with st.spinner("Generating message..."):
        initial_state: ProspectMessageState = {
            "prospect_name": prospect_name,
            "designation": designation,
            "company": company,
            "industry": industry,
            "prospect_background": prospect_background,
            "my_background": my_background,
            "event_name": event_name,
            "event_details": event_details,
        }
        result = graph1.invoke(initial_state)

    st.success(" Message Generated!")
    st.text_area("Final LinkedIn Message", result["final_message"], height=200, key="final_msg")

    # Copy button using JavaScript
    copy_code = f"""
    <script>
    function copyToClipboard() {{
        var text = `{result['final_message']}`;
        navigator.clipboard.writeText(text).then(() => {{
            alert("Message copied to clipboard!");
        }});
    }}
    </script>
    <button onclick="copyToClipboard()"> Copy Message</button>
    """

    st.components.v1.html(copy_code, height=50)

