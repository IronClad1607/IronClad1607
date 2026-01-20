import os
import requests
import datetime
import re # We import Regex to handle the text replacement safely

# --- Configuration ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
USERNAME = os.getenv("GITHUB_ACTOR")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# --- GraphQL Queries ---
# (Queries remain the same as before)
user_query = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(first: 100, ownerAffiliations: [OWNER, COLLABORATOR], isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""

contribution_query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
"""

def run_query(query, variables):
    response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed: {response.status_code} {response.text}")

# --- Main Logic ---
print(f"Fetching data for {USERNAME}...")

# 1. Get User Basics
user_data = run_query(user_query, {"login": USERNAME})["data"]["user"]
created_at_dt = datetime.datetime.fromisoformat(user_data["createdAt"].replace("Z", "+00:00"))
current_dt = datetime.datetime.now(datetime.timezone.utc)
years_joined = current_dt.year - created_at_dt.year

# 2. Process Languages
languages = {}
total_size = 0
total_stars = 0
total_repos = 0

for repo in user_data["repositories"]["nodes"]:
    total_repos += 1
    total_stars += repo["stargazerCount"]
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        size = edge["size"]
        color = edge["node"]["color"]
        if name not in languages:
            languages[name] = {"size": 0, "color": color}
        languages[name]["size"] += size
        total_size += size

sorted_languages = sorted(languages.items(), key=lambda item: item[1]["size"], reverse=True)

# 3. Iterate Years for Lifetime Stats
total_commits = 0
total_prs = 0
total_issues = 0

for year in range(created_at_dt.year, current_dt.year + 1):
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"
    if year == created_at_dt.year: start_date = user_data["createdAt"]
    if year == current_dt.year: end_date = current_dt.isoformat()

    print(f"Fetching stats for {year}...")
    stats = run_query(contribution_query, {"login": USERNAME, "from": start_date, "to": end_date})["data"]["user"]["contributionsCollection"]
    total_commits += stats["totalCommitContributions"] + stats["restrictedContributionsCount"]
    total_prs += stats["totalPullRequestContributions"]
    total_issues += stats["totalIssueContributions"]

# 4. Generate Badge Block
lang_badges = ""
for name, info in sorted_languages[:8]:
    percent = (info["size"] / total_size) * 100 if total_size > 0 else 0
    color = info["color"].replace("#", "") if info["color"] else "cccccc"
    safe_name = name.replace(" ", "%20").replace("-", "--")
    badge = f"![{name}](https://img.shields.io/static/v1?style=flat-square&label=%E2%A0%80&color=555&labelColor=%23{color}&message={safe_name}%EF%B8%B1{percent:.1f}%25)"
    lang_badges += badge + "\n"

# 5. Create New Content
markdown_text = f"""
Hi There!

Joined Github **{years_joined}** years ago.

Since then I pushed **{total_commits}** commits, opened **{total_issues}** issues, submitted **{total_prs}** pull requests, received **{total_stars}** stars across **{total_repos}** personal projects.

Most used languages across my projects:

{lang_badges}
"""

# 6. SAFELY UPDATE README using REGEX
print("Updating README...")

with open("README.md", "r", encoding="utf-8") as f:
    readme_content = f.read()

# Regex Pattern: Finds "Start Marker" + Anything in between + "End Marker"
# re.DOTALL allows the dot (.) to match newlines
pattern = r"()(.*?)()"
replacement = f"\\1\n{markdown_text}\n\\3"

# Check if markers exist
if re.search(pattern, readme_content, flags=re.DOTALL):
    new_content = re.sub(pattern, replacement, readme_content, flags=re.DOTALL)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("README updated successfully.")
else:
    print("ERROR: Could not find and in README.md")