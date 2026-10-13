from app.memory.service import MemoryService
from app.memory.time_parser import get_yesterday_range

memory = MemoryService()

start_time, end_time = get_yesterday_range()

print(f"\nYesterday UTC: {start_time} to {end_time}")

messages = memory.search_in_time_range(
text="What did we discuss yesterday?",
start_time=start_time,
end_time=end_time,
top_k=30,
min_score=0.0,
)

print(f"\nMessages found: {len(messages)}\n")

for message in messages:
    print(
    f"[{message['created_at']}] "
    f"{message['role']}: "
    f"{message['content'][:250]}"
)
