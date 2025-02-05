### Problem Description

Enable the automated processing of current and past Slack conversations in to a vector database for questions and
answers via a slack bot slash command or other front-ends like the command-line. The prompt and the conversations should
be crafted in such a way to allow themselves to be understood easily by modern LLMs.

## Functional Requirements

- Conversations should be stored in such a method that the context and flow of the conversation is maintained.
- The slack user id should be obfuscated before it's included in the conversation but relevant to the current
  conversation. For example:
- Additional metadate such as the date, channel id, channel name, channel description as well as other details that the
  slack api returns and is relevant to the problem description should be included and persisted.
- References in the [references](references) folder should be included when considering implementation and design decisions.

```
User_1 Start the topic with: <message goes here> 
User_2 Replies with: <reply goes here> and so on.
```

- The ingestion process should be able to handle a start date and one or more channels where it can backfill
  conversations for the configured channels.

## Non-Functional Requirements

- Python should be used as well as libraries available in the python ecosystem should be used.
- Dotenv should be used to manage environment variables.
- A .env.sample file should contain all the required environment variables.
- General Python best practices and OO principles should be followed.
- There should be utility script to set the system back to a pristine state.
- All scripts should be runnable as-is with a trivial example main function for developer testing.