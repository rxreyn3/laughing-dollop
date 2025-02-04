#!/usr/bin/env python3
import os
from datetime import datetime
from typing import Dict, Any, List

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import llama_config as config
import query
from log_config import setup_logger

# Set up logger
logger = setup_logger(__name__)

# Load environment variables
load_dotenv()

# Initialize the Slack app
app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Initialize LlamaIndex
index = query.setup_llamaindex()

# Channel for feedback
FEEDBACK_CHANNEL = "C06FDLYTD32"
WORKSPACE_URL = "electronic-arts"


def create_source_link(thread_ts: str, channel_id: str) -> str:
    """Create a Slack permalink to the source conversation."""
    return f"https://{WORKSPACE_URL}.slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"


def format_source_section(source_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format source nodes into Slack blocks for display."""
    blocks = []
    
    # Add header
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*📚 Relevant Sources:*"
        }
    })
    
    # Add source links with relevance scores in a single block
    source_links = []
    for idx, node in enumerate(source_nodes, 1):
        metadata = node.metadata
        score = node.score if hasattr(node, 'score') else None
        score_text = f" ({score:.2f})" if score is not None else ""
        
        source_links.append(
            f"<{create_source_link(metadata['thread_ts'], metadata['channel_id'])}|Source {idx}>{score_text}"
        )
    
    # Join all sources with bullet points
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "• " + "\n• ".join(source_links)
        }
    })
    
    return blocks


def create_feedback_buttons() -> Dict[str, Any]:
    """Create feedback buttons block."""
    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "👍 Helpful",
                    "emoji": True
                },
                "style": "primary",
                "value": "helpful",
                "action_id": "feedback_helpful"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "👎 Not Helpful",
                    "emoji": True
                },
                "style": "danger",
                "value": "not_helpful",
                "action_id": "feedback_not_helpful"
            }
        ]
    }


def post_feedback_to_channel(
    question: str, 
    answer: str, 
    feedback: str, 
    user_id: str,
    timestamp: str
) -> None:
    """Post feedback to the designated channel."""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔄 Bot Interaction Feedback",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*User:* <@{user_id}>"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Feedback:* {'👍 Helpful' if feedback == 'helpful' else '👎 Not Helpful'}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Question:*\n{question}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Answer:*\n{answer}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Interaction timestamp: {datetime.fromtimestamp(float(timestamp))}"
                }
            ]
        }
    ]
    
    app.client.chat_postMessage(
        channel=FEEDBACK_CHANNEL,
        blocks=blocks,
        text="New bot interaction feedback"  # Fallback text
    )


@app.command("/jarvis")
def handle_jarvis_command(ack, command, say):
    """Handle the /jarvis slash command."""
    # Acknowledge command receipt
    ack()
    
    question = command["text"].strip()
    if not question:
        say("Please provide a question after the /jarvis command.")
        return
    
    try:
        logger.info(f"Processing command from user {command['user_id']}: {question}")
        
        # Get answer using existing query system
        logger.debug("Calling query system...")
        response = query.ask_question(index, question)
        
        if response.error:
            logger.error(f"Query system returned error: {response.error}")
            say(f"Sorry, I encountered an error: {response.error}")
            return
            
        logger.debug(f"Got response with {len(response.source_nodes)} source nodes")
        
        # Create blocks for the response
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🤖 Jarvis Response",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question:*\n{question}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Answer:*\n{response.response}"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add source sections if we have any
        if response.source_nodes:
            blocks.extend(format_source_section(response.source_nodes))
        else:
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": "_No source conversations found for this answer._"
                }]
            })
        
        # Add feedback buttons
        blocks.append(create_feedback_buttons())
        
        # Send response
        logger.debug("Sending response to Slack")
        say(
            blocks=blocks,
            text=response.response  # Fallback text
        )
        logger.info("Response sent successfully")
        
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}", exc_info=True)
        say("Sorry, I encountered an error while processing your question. Please try again later.")


@app.action("feedback_helpful")
def handle_helpful_feedback(ack, body, client):
    """Handle helpful feedback button click."""
    ack()
    process_feedback(body, "helpful")


@app.action("feedback_not_helpful")
def handle_not_helpful_feedback(ack, body, client):
    """Handle not helpful feedback button click."""
    ack()
    process_feedback(body, "not_helpful")


def process_feedback(body: Dict[str, Any], feedback_type: str):
    """Process feedback from button clicks."""
    # Extract relevant information
    message = body["message"]
    user_id = body["user"]["id"]
    timestamp = body["message"]["ts"]
    
    # Find question and answer from the message blocks
    question = ""
    answer = ""
    for block in message["blocks"]:
        if block["type"] == "section":
            text = block["text"]["text"]
            if text.startswith("*Question:*\n"):
                question = text.replace("*Question:*\n", "")
            elif text.startswith("*Answer:*\n"):
                answer = text.replace("*Answer:*\n", "")
    
    # Post feedback to private channel
    post_feedback_to_channel(question, answer, feedback_type, user_id, timestamp)
    
    # Update the original message to show feedback was received
    blocks = message["blocks"]
    # Remove the old feedback buttons
    blocks = [b for b in blocks if b.get("type") != "actions"]
    # Add a confirmation message
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Thanks for your feedback! {'👍' if feedback_type == 'helpful' else '👎'}"
            }
        ]
    })
    
    # Update the message
    app.client.chat_update(
        channel=body["channel"]["id"],
        ts=timestamp,
        blocks=blocks,
        text=message.get("text", "")
    )


def main():
    """Main entry point for the Slack bot."""
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Starting Slack bot...")
    handler.start()


if __name__ == "__main__":
    main()
