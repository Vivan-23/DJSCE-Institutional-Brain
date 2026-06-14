import os
import random
from datetime import datetime, timedelta

output_dir = "c:/Everything/Important/Projects/to be added/Company Brain/mock_company_data"
os.makedirs(output_dir, exist_ok=True)

employees = [
    {"name": "Sarah Jenkins", "role": "Frontend Lead"},
    {"name": "Marcus Chen", "role": "Backend Lead"},
    {"name": "Alex Rivera", "role": "Security Engineer"},
    {"name": "David Kim", "role": "Product Manager"},
    {"name": "Emily Carter", "role": "Frontend Engineer"},
    {"name": "Michael Chang", "role": "Backend Engineer"},
    {"name": "Jessica Lee", "role": "QA Engineer"},
    {"name": "Ryan Gosling", "role": "UX Designer"},
    {"name": "Amanda Smith", "role": "DevOps Engineer"},
    {"name": "James Wilson", "role": "Data Scientist"},
    {"name": "Olivia Brown", "role": "Product Owner"},
    {"name": "William Davis", "role": "Backend Engineer"},
    {"name": "Sophia Miller", "role": "Frontend Engineer"},
    {"name": "Daniel Wilson", "role": "QA Lead"},
    {"name": "Isabella Moore", "role": "HR Manager"},
    {"name": "Matthew Taylor", "role": "Backend Engineer"},
    {"name": "Emma Anderson", "role": "Frontend Engineer"},
    {"name": "Joshua Thomas", "role": "Security Engineer"},
    {"name": "Mia Jackson", "role": "UX Designer"},
    {"name": "Andrew White", "role": "Engineering Manager"}
]

projects = ["Project Alpha", "Project Beta", "Legacy System Migration", "Data Pipeline Revamp"]

start_date = datetime(2025, 11, 1)
end_date = datetime(2026, 5, 20)
current_date = start_date

updates = [
    "Refactored the core authentication module.",
    "Fixed a critical bug in the payment gateway.",
    "Drafted UI components for the new dashboard.",
    "Conducted user interviews for the redesign.",
    "Deployed the new database schema to staging.",
    "Investigated memory leak in the worker nodes.",
    "Wrote unit tests for the billing service.",
    "Optimized the search query performance by 30%.",
    "Blocked by DevOps on provision of new CI/CD runners.",
    "Waiting on design assets for the landing page.",
    "Successfully migrated 10k users to the new system.",
    "Reviewing pull requests for the latest sprint.",
    "Attended cross-functional sync with the marketing team.",
    "Updated the API documentation for the v2 release."
]

meeting_topics = [
    "Sprint Planning",
    "Architecture Review",
    "Post-mortem",
    "Daily Standup Summary",
    "Design Sync",
    "Cross-team Alignment"
]

file_count = 0

while current_date <= end_date:
    # 1. Weekly Status Report per project (every Friday)
    if current_date.weekday() == 4:
        for project in projects:
            file_name = f"Weekly_Status_{project.replace(' ', '_')}_{current_date.strftime('%Y-%m-%d')}.txt"
            team = random.sample(employees, k=random.randint(3, 7))
            team_names = ", ".join([e["name"] for e in team])
            status = random.choice(["On Track", "At Risk", "Delayed", "Completed"])
            
            content = f"# Weekly Status Report: {project}\n**Date**: {current_date.strftime('%B %d, %Y')}\n**Status**: {status}\n\n## Team Members\n{team_names}\n\n## Updates\n"
            for member in team:
                update = random.choice(updates)
                content += f"- **{member['name']}**: {update}\n"
                
            with open(os.path.join(output_dir, file_name), "w") as f:
                f.write(content)
            file_count += 1

    # 2. Random Meeting Notes (20% chance per day)
    if random.random() < 0.2:
        topic = random.choice(meeting_topics)
        file_name = f"Meeting_Notes_{topic.replace(' ', '_')}_{current_date.strftime('%Y-%m-%d')}.txt"
        attendees = random.sample(employees, k=random.randint(4, 10))
        attendee_names = ", ".join([e["name"] for e in attendees])
        
        content = f"# {topic} - {current_date.strftime('%B %d, %Y')}\n\n**Attendees**: {attendee_names}\n\n## Discussion Points\n"
        for _ in range(random.randint(2, 5)):
            speaker = random.choice(attendees)["name"]
            point = random.choice(updates)
            content += f"- **{speaker}**: {point}\n"
            
        content += "\n## Action Items\n"
        for _ in range(random.randint(1, 3)):
            assignee = random.choice(attendees)["name"]
            content += f"- [ ] {assignee} to follow up on related tasks.\n"
            
        with open(os.path.join(output_dir, file_name), "w") as f:
            f.write(content)
        file_count += 1
        
    current_date += timedelta(days=1)

print(f"Successfully generated {file_count} mock documents in {output_dir}")
