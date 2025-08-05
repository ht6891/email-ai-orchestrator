# evaluate.py
#
# Usage:
#   $ pip install pandas
#   $ python evaluate.py
#
# This script requires:
#   - app.py (so that summarize_text and analyze_sentiment are in scope)
#   - A JSON file (or embedded list) of sample emails with gold summaries + gold sentiment
#

import json
import re
import pandas as pd
from app import summarize_text, analyze_sentiment

def jaccard_similarity(a: str, b: str) -> float:
    """
    Compute Jaccard similarity between two texts a and b:
    J(A,B) = |A ∩ B| / |A ∪ B|, where A and B are sets of tokens.
    """
    set_a = set(re.findall(r"\w+", a.lower()))
    set_b = set(re.findall(r"\w+", b.lower()))
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)

def run_evaluation():
    """
    Load sample emails, run summarization & sentiment,
    compute Jaccard and sentiment accuracy, and print results.
    """
    # Hardcode 20 sample email entries for evaluation, each with:
    #   "email": str, "gold_summary": str, "gold_sentiment": "positive"/"neutral"/"negative"

    samples = [
        {
            "email": "Hi John, Can you review the attached report by tomorrow? We need to send it to the client. Thanks! Regards, Alice",
            "gold_summary": "Alice requests John to review the attached report by tomorrow for client submission.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Hello Team, I’m disappointed that the server was down last night for 3 hours. We lost many sales. Please address this ASAP. Thanks, Bob",
            "gold_summary": "Bob reports server downtime of 3 hours, lost sales, and asks for immediate fix.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Dear all, Thank you for attending yesterday’s meeting. The minutes are attached. Let me know if you have corrections. Best, Carol",
            "gold_summary": "Carol thanks attendees, shares attached meeting minutes, and asks for corrections.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Hi, The Q1 sales numbers were excellent! We exceeded our target by 20%. Great work, team. Cheers, Diana",
            "gold_summary": "Diana announces Q1 sales beat target by 20% and congratulates the team.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Team, Please note: The build failed on Jenkins again. We cannot deploy until this is fixed. Urgent. Regards, Ethan",
            "gold_summary": "Ethan reports Jenkins build failure, blocking deployment, calls for urgent fix.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Hi! Please find the invoice for last month attached. Let me know if you need any clarifications. Thanks, Finance Dept",
            "gold_summary": "Finance Dept sent last month’s invoice and invites questions.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Dear Sarah, Congratulations on your promotion! We’re thrilled to have you lead the marketing team. Best wishes, CEO",
            "gold_summary": "CEO congratulates Sarah on her promotion to lead marketing.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Hello, There will be a maintenance window this Saturday from 2 AM to 4 AM. Services may be unavailable. Apologies for inconvenience. IT Team",
            "gold_summary": "IT Team announces Saturday maintenance window (2–4 AM) and warns of downtime.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Good afternoon, The office will be closed next Monday for a public holiday. Normal business resumes Tuesday. Regards, HR",
            "gold_summary": "HR notifies that the office is closed next Monday for holiday; business resumes Tuesday.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Hi Team, We have a new security vulnerability reported. Please patch the servers by end of day. Urgent. Security Team",
            "gold_summary": "Security Team reports new vulnerability and demands server patch by end of day.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Dear All, Congratulations! Our paper was accepted at the IEEE conference next month. Let's prepare slides. Cheers, Alice",
            "gold_summary": "Alice announces paper acceptance to IEEE conference and reminds team to prepare slides.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Hello John, I am currently out of office until Friday. For urgent matters, contact Jane. Best, Michael",
            "gold_summary": "Michael is out of office until Friday and directs urgent issues to Jane.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Team, We missed our monthly KPI targets again. Sales dropped by 10%. We must come up with a new strategy. Regards, Director",
            "gold_summary": "Director laments missing KPI targets, notes 10% sales drop, and calls for new strategy.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Hi Mary, Thank you for the comprehensive handover document. I’ll review it tonight and get back to you. Best, Tom",
            "gold_summary": "Tom thanks Mary for handover document and promises to review it tonight.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Dear Vendor, We did not receive the shipment you promised last week. This delay is unacceptable. Please respond by EOD. Sincerely, Ops",
            "gold_summary": "Ops complains vendor shipment is overdue, deems delay unacceptable, and demands response by EOD.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Greetings, We will have a team‐building event this Friday in the conference room. Bring your ideas for activities. Cheers, Event Coordinator",
            "gold_summary": "Event Coordinator announces Friday team-building event in conference room and asks for activity ideas.",
            "gold_sentiment": "positive"
        },
        {
            "email": "Hi Sam, I noticed several typos in the last presentation deck. Can you correct them before tomorrow’s client call? Regards, QA Lead",
            "gold_summary": "QA Lead points out typos in presentation deck and asks Sam to correct before tomorrow’s client call.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Team, The customer escalated due to slow response on ticket #1234. We need to prioritize this now. Thanks, Support Lead",
            "gold_summary": "Support Lead reports customer escalation on ticket #1234 and instructs team to prioritize it immediately.",
            "gold_sentiment": "negative"
        },
        {
            "email": "Hello, Our annual performance reviews are next week. Please submit your self‐evaluation by Wednesday. HR Team",
            "gold_summary": "HR Team informs that annual performance reviews are next week and asks for self‐evaluations by Wednesday.",
            "gold_sentiment": "neutral"
        },
        {
            "email": "Hi, FYI, the DevOps script now auto‐restarts the server if it crashes. No manual intervention needed. Cheers, DevOps",
            "gold_summary": "DevOps announces new script auto‐restarts server on crash, eliminating need for manual intervention.",
            "gold_sentiment": "positive"
        }
    ]

    results = []
    correct_sentiment = 0

    for idx, entry in enumerate(samples):
        email_text = entry["email"]
        gold_sum = entry["gold_summary"]
        gold_sent = entry["gold_sentiment"]

        # Summarization
        generated_sum = summarize_text(email_text)
        j_score = round(jaccard_similarity(generated_sum, gold_sum), 2)

        # Sentiment
        sent_out = analyze_sentiment(email_text)
        pred_cat = sent_out["mapped_category"]
        if pred_cat == gold_sent:
            correct_sentiment += 1

        results.append({
            "Index": idx + 1,
            "Email": email_text.replace("\n", " "),
            "Gold Summary": gold_sum,
            "Gen. Summary": generated_sum,
            "Jaccard": j_score,
            "Gold Sentiment": gold_sent,
            "Pred Sentiment": pred_cat,
            "Sent Label": sent_out.get("label", ""),
            "Sent Score": round(sent_out.get("score", 0), 2)
        })

    df = pd.DataFrame(results)
    accuracy = correct_sentiment / len(samples)
    print("\n===== Evaluation Results =====\n")
    print(df[[
        "Index", "Jaccard", "Gold Sentiment", "Pred Sentiment",
        "Sent Label", "Sent Score"
    ]].to_markdown(index=False))

    print(f"\nOverall Sentiment Accuracy: {accuracy:.2f} ({correct_sentiment}/{len(samples)})\n")
    print(df[["Index", "Email", "Gold Summary", "Gen. Summary"]].to_markdown(index=False))


if __name__ == "__main__":
    run_evaluation()
