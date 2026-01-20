import os
import requests
import datetime
import sys

# --- Configuration ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
USERNAME = os.getenv("GITHUB_ACTOR")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# --- Define Markers (DO NOT CHANGE THESE) ---
START_MARKER = "<!--START_SECTION:my_stats-->"
END_MARKER = "<!--END_SECTION:my_stats-->"

# --- Safety Check ---
if not START_MARKER or not END_MARKER:
    print("CRITICAL ERROR: Markers are empty. Do not modify the START_MARKER line.")
    sys.exit(1)

# --- GraphQL Queries ---
user_query = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(first: 100, ownerAffiliations: [OWNER, COLLABORATOR], isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name, color }
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

def run_query(query, var):
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': var}, headers=HEADERS)
    if request.status_code == 200: return request.json()
    else: raise Exception(f"Query failed: {request.status_code}")

# --- Main Logic ---
print(f"Fetching data for {USERNAME}...")

try:
    # 1. Get User Basics
    user_data = run_query(user_query, {"login": USERNAME})["data"]["user"]
    created_at = datetime.datetime.fromisoformat(user_data["createdAt"].replace("Z", "+00:00"))
    now = datetime.datetime.now(datetime.timezone.utc)
    years_joined = now.year - created_at.year

    # 2. Loop through Years
    total_commits = 0
    total_prs = 0
    total_issues = 0
    total_stars = 0
    languages = {}
    total_size = 0

    # Process Repos
    total_repos = len(user_data["repositories"]["nodes"])
    for repo in user_data["repositories"]["nodes"]:
        total_stars += repo["stargazerCount"]
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            size = edge["size"]
            color = edge["node"]["color"]
            if name not in languages: languages[name] = {"size": 0, "color": color}
            languages[name]["size"] += size
            total_size += size

    # Process Stats per Year
    for year in range(created_at.year, now.year + 1):
        loop_start = f"{year}-01-01T00:00:00Z"
        loop_end = f"{year}-12-31T23:59:59Z"
        if year == created_at.year: loop_start = user_data["createdAt"]
        if year == now.year: loop_end = now.isoformat()
        
        print(f"Fetching year {year}...")
        data = run_query(contribution_query, {"login": USERNAME, "from": loop_start, "to": loop_end})["data"]["user"]["contributionsCollection"]
        total_commits += data["totalCommitContributions"] + data["restrictedContributionsCount"]
        total_prs += data["totalPullRequestContributions"]
        total_issues += data["totalIssueContributions"]

    # 3. Generate Badges
    sorted_langs = sorted(languages.items(), key=lambda x: x[1]["size"], reverse=True)[:8]
    badges = ""
    for name, info in sorted_langs:
        pct = (info["size"] / total_size) * 100 if total_size > 0 else 0
        color = info["color"].replace("#", "") if info["color"] else "cccccc"
        safe_name = name.replace(" ", "%20").replace("-", "--")
        badges += f"![{name}](https://img.shields.io/static/v1?style=flat-square&label=%E2%A0%80&color=555&labelColor=%23{color}&message={safe_name}%EF%B8%B1{pct:.1f}%25)\n"

    # 4. Generate Final Markdown
    new_stats = f"""
Hi There!

Joined Github **{years_joined}** years ago.

Since then I pushed **{total_commits}** commits, opened **{total_issues}** issues, submitted **{total_prs}** pull requests, received **{total_stars}** stars across **{total_repos}** personal projects.

Most used languages across my projects:

{badges}
"""

    # 5. Update README
    print("Reading README.md...")
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER in content and END_MARKER in content:
        print("Found markers. Updating content...")
        # Split safely
        parts_start = content.split(START_MARKER)
        parts_end = content.split(END_MARKER)
        
        # Reconstruct: Everything before Start + Start + New Stats + End + Everything after End
        # Note: We use rsplit on the first part and split on the last part to handle potential duplicates safely
        pre = parts_start[0]
        post = parts_end[-1] 
        
        final_content = pre + START_MARKER + "\n" + new_stats + "\n" + END_MARKER + post
        
        with open("README.md", "w", encoding="utf-8") as f:
            f.write(final_content)
        print("README updated successfully!")
    else:
        print("ERROR: Could not find markers in README.md")
        print(f"Looking for: {START_MARKER}")
        print("Please verify README.md contains these exact lines.")

except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)