import json
from app.core.config import settings


class MemoryExtractor:
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client

    def extract(self, user_message: str):
        prompt = f"""
        You are a strict structured-memory classifier for EDITH.

        Your task is NOT to answer the user's message.

        Your ONLY task is to identify information that the user explicitly
        states about themselves or their long-term projects/relationships
        that is worth remembering across future conversations.

        The user message may contain:
        - a statement
        - a question
        - a request
        - temporary information
        - casual conversation
        - technical discussion
        - multiple statements

        ==================================================
        CORE RULE
        ==================================================

        Only create a memory when ALL of these are true:

        1. The information is explicitly stated by the user.
        2. It describes the user, the user's stable preference,
        the user's long-term project, or an important person/relationship.
        3. It is likely to remain useful beyond the current conversation.
        4. It is not merely temporary, current, or conversational.

        If these conditions are not satisfied, return:

        {{"memories": []}}

        ==================================================
        NEVER STORE
        ==================================================

        NEVER create memory from:

        - Questions
        - Requests for information
        - Requests for advice
        - General knowledge
        - Explanations
        - Hypothetical statements
        - Greetings
        - Jokes
        - Casual conversation
        - Current mood
        - Current feelings
        - Current time
        - Current battery percentage
        - Today's activities
        - Tomorrow's activities
        - One-time events
        - Temporary plans
        - What the user ate today
        - What the user is doing right now
        - What the user is currently testing
        - A technical concept merely being discussed
        - Information that comes from the assistant rather than the user

        IMPORTANT:

        A technical conversation is NOT automatically a memory.

        For example, discussing JWT does NOT mean the user prefers JWT,
        uses JWT, or has a JWT project.

        Similarly, discussing Python does NOT mean Python is the user's
        preferred language.

        Only explicit user statements about themselves count.

        ==================================================
        WHAT SHOULD BE STORED
        ==================================================

        Store stable information such as:

        - User identity facts
        - Stable preferences
        - Long-term projects
        - Stable technology choices for the user's projects
        - Important people and relationships
        - Persistent choices or configurations

        ==================================================
        TEMPORAL RULE
        ==================================================

        If the information contains words such as:

        today
        tonight
        tomorrow
        currently
        right now
        this morning
        this evening
        at the moment

        treat it as temporary and DO NOT store it,

        UNLESS the message clearly establishes a durable fact that remains
        useful beyond that time reference.

        ==================================================
        QUESTION RULE
        ==================================================

        If the message is asking a question, return:

        {{"memories": []}}

        Do NOT turn the subject of a question into a memory.

        ==================================================
        MULTIPLE MEMORIES
        ==================================================

        One message can contain multiple independent durable facts.

        Create one memory object for each independent fact.

        Do not combine unrelated facts into one memory.

        ==================================================
        MEMORY TYPES
        ==================================================

        The type MUST be exactly one of:

        fact
        preference
        project
        person

        Do not invent other types.

        ==================================================
        KEY RULE
        ==================================================

        The key must:

        - be short
        - be lowercase
        - use snake_case
        - describe the actual fact
        - be stable enough to identify the same memory later

        ==================================================
        VALUE RULE
        ==================================================

        The value must contain ONLY the information explicitly stated
        by the user.

        NEVER invent information.

        NEVER infer a preference.

        NEVER answer the user's question yourself.

        ==================================================
        OUTPUT FORMAT
        ==================================================

        Return ONLY valid JSON.

        The root object MUST contain exactly one field:

        memories

        memories MUST always be an array.

        Each memory MUST contain exactly:

        type
        key
        value

        If nothing qualifies as durable memory:

        {{"memories": []}}

        USER MESSAGE:

        {user_message}
        """

        response = self.ollama_client.generate(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )

        try:
            result = json.loads(response)

            if not isinstance(result, dict):
                return {"memories": []}

            memories = result.get("memories")

            if not isinstance(memories, list):
                return {"memories": []}

            valid_memories = []

            for memory in memories:
                if not isinstance(memory, dict):
                    continue

                memory_type = memory.get("type")
                key = memory.get("key")
                value = memory.get("value")

                if memory_type not in {
                    "fact",
                    "preference",
                    "project",
                    "person",
                }:
                    continue

                if not isinstance(key, str) or not key.strip():
                    continue

                if not isinstance(value, str) or not value.strip():
                    continue

                valid_memories.append({
                    "type": memory_type,
                    "key": key.strip(),
                    "value": value.strip(),
                })

            return {
                "memories": valid_memories,
            }

        except json.JSONDecodeError:
            return {
                "memories": [],
            }