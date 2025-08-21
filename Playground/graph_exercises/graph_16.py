from typing_extensions import TypedDict
from typing import List
from langgraph.graph import StateGraph, START, END

# Simple customer feedback processing example

# Data structure for feedback
class Feedback(TypedDict):
    id: str
    text: str
    rating: int  # 1-5 stars

# ===== SENTIMENT ANALYSIS SUBGRAPH =====
class SentimentState(TypedDict):
    feedback_list: List[Feedback]

def analyze_sentiment(state):
    """Analyze sentiment of all feedback"""
    feedback_list = state["feedback_list"]
    
    # Simple sentiment analysis (in real app, use AI model)
    positive_count = sum(1 for f in feedback_list if f["rating"] >= 4)
    negative_count = sum(1 for f in feedback_list if f["rating"] <= 2)
    total = len(feedback_list)
    
    sentiment_summary = f"Sentiment Analysis: {positive_count}/{total} positive, {negative_count}/{total} negative"
    return {"sentiment_summary": sentiment_summary}

# Build sentiment analysis subgraph
sentiment_builder = StateGraph(SentimentState, output_schema=TypedDict("SentimentOutput", {"sentiment_summary": str}))
sentiment_builder.add_node("analyze_sentiment", analyze_sentiment)
sentiment_builder.add_edge(START, "analyze_sentiment")
sentiment_builder.add_edge("analyze_sentiment", END)

# ===== TOPIC ANALYSIS SUBGRAPH =====
class TopicState(TypedDict):
    feedback_list: List[Feedback]

def extract_topics(state):
    """Extract main topics from feedback"""
    feedback_list = state["feedback_list"]
    
    # Simple keyword extraction (in real app, use NLP)
    keywords = []
    for feedback in feedback_list:
        text = feedback["text"].lower()
        if "price" in text or "cost" in text:
            keywords.append("pricing")
        if "support" in text or "help" in text:
            keywords.append("customer_service")
        if "fast" in text or "slow" in text:
            keywords.append("performance")
        if "bug" in text or "error" in text:
            keywords.append("technical_issues")
    
    # Count frequency
    topic_counts = {}
    for keyword in keywords:
        topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
    
    topic_summary = f"Main Topics: {dict(topic_counts)}"
    return {"topic_summary": topic_summary}

# Build topic analysis subgraph
topic_builder = StateGraph(TopicState, output_schema=TypedDict("TopicOutput", {"topic_summary": str}))
topic_builder.add_node("extract_topics", extract_topics)
topic_builder.add_edge(START, "extract_topics")
topic_builder.add_edge("extract_topics", END)

# ===== MAIN GRAPH =====
class MainState(TypedDict):
    raw_feedback: List[Feedback]
    feedback_list: List[Feedback]  # Cleaned data
    sentiment_summary: str         # From sentiment subgraph
    topic_summary: str            # From topic subgraph
    final_report: str             # Final combined report

def clean_feedback(state):
    """Clean and filter feedback data"""
    raw_feedback = state["raw_feedback"]
    
    # Simple cleaning: remove empty feedback
    cleaned = [f for f in raw_feedback if f["text"].strip()]
    
    return {"feedback_list": cleaned}

def generate_report(state):
    """Combine results from both subgraphs into final report"""
    sentiment = state["sentiment_summary"]
    topics = state["topic_summary"]
    
    report = f"""
CUSTOMER FEEDBACK ANALYSIS REPORT
=================================
{sentiment}
{topics}

RECOMMENDATION: Focus on the most mentioned topics with negative sentiment.
"""
    return {"final_report": report}

# Build main graph
main_builder = StateGraph(MainState)
main_builder.add_node("clean_feedback", clean_feedback)
main_builder.add_node("sentiment_analysis", sentiment_builder.compile())
main_builder.add_node("topic_analysis", topic_builder.compile())
main_builder.add_node("generate_report", generate_report)

# Define the flow
main_builder.add_edge(START, "clean_feedback")
main_builder.add_edge("clean_feedback", "sentiment_analysis")
main_builder.add_edge("clean_feedback", "topic_analysis")
main_builder.add_edge("sentiment_analysis", "generate_report")
main_builder.add_edge("topic_analysis", "generate_report")
main_builder.add_edge("generate_report", END)

# Compile the main graph
graph = main_builder.compile()

# ===== EXAMPLE USAGE =====
if __name__ == "__main__":
    # Sample feedback data
    sample_feedback = [
        {"id": "1", "text": "Great product but too expensive", "rating": 3},
        {"id": "2", "text": "Customer support was very helpful", "rating": 5},
        {"id": "3", "text": "App is too slow, lots of bugs", "rating": 2},
        {"id": "4", "text": "Love the fast performance!", "rating": 5},
        {"id": "5", "text": "Price is reasonable for the quality", "rating": 4},
    ]
    
    # Run the analysis
    result = graph.invoke({
        "raw_feedback": sample_feedback
    })
    
    print("FINAL ANALYSIS RESULT:")
    print("=" * 50)
    print(result["final_report"])
    
    # You can also see intermediate results
    print("\nINTERMEDIATE RESULTS:")
    print(f"Cleaned feedback count: {len(result['feedback_list'])}")
    print(f"Sentiment: {result['sentiment_summary']}")
    print(f"Topics: {result['topic_summary']}")