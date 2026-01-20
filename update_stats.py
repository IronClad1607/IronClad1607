import os
import requests
import datetime

# --- Configuration ---
# To show private stats (work experience), you need a PAT. 
# If using the default GITHUB_TOKEN, this will only show Public stats.
GITHUB_TOKEN = os.getenv("GH_TOKEN") 
USERNAME = os.getenv("GITHUB_ACTOR")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# --- GraphQL Queries ---

# 1. Query for Account Creation Date & Repositories (Language Stats)
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

# 2. Query for Yearly Contributions (Iterative)
contribution_query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
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

# 1. Get User Basics & Repos
user_data = run_query(user_query, {"login": USERNAME})["data"]["user"]
created_at_str = user_data["createdAt"]
created_at_dt = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
current_dt = datetime.datetime.now(datetime.timezone.utc)

years_joined = current_dt.year - created_at_dt.year

# 2. Calculate Languages & Stars
languages = {}
total_size = 0
total_stars = 0
total_personal_repos = 0

for repo in user_data["repositories"]["nodes"]:
    total_personal_repos += 1
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
contributed_repos = set() # Use a set to avoid duplicates across years

# Loop from join year to current year
for year in range(created_at_dt.year, current_dt.year + 1):
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"
    
    # Adjust for creation year (don't ask for data before account existed)
    if year == created_at_dt.year:
        start_date = created_at_str
    
    # Adjust for current year (don't ask for future)
    if year == current_dt.year:
        end_date = current_dt.isoformat()

    print(f"Fetching stats for {year}...")
    stats = run_query(contribution_query, {"login": USERNAME, "from": start_date, "to": end_date})["data"]["user"]["contributionsCollection"]
    
    # Sum it up
    # Note: restrictedContributionsCount = Private commits (requires PAT to see accurate numbers)
    total_commits += stats["totalCommitContributions"] + stats["restrictedContributionsCount"]
    total_prs += stats["totalPullRequestContributions"]
    total_issues += stats["totalIssueContributions"]
    
    # Note: The API gives a count, not a list, so we sum the counts. 
    # This is an approximation for "Contributed Repos" as deduplicating completely requires a much heavier query.
    # For display purposes, taking the max or sum of unique contributions per year is standard.
    pass 

# 4. Generate Badge Block
lang_badges = ""
for name, info in sorted_languages[:8]: # Top 8
    if total_size > 0:
        percent = (info["size"] / total_size) * 100
    else:
        percent = 0
    
    # Fix colors for specific langs if needed, otherwise use GitHub color
    color = info["color"] if info["color"] else "#cccccc"
    color = color.replace("#", "")
    
    # URL Encode spaces for badges
    safe_name = name.replace(" ", "%20").replace("-", "--")
    
    badge = f"![{name}](https://img.shields.io/static/v1?style=flat-square&label=%E2%A0%80&color=555&labelColor=%23{color}&message={safe_name}%EF%B8%B1{percent:.1f}%25)"
    lang_badges += badge + "\n"

# 5. Create Markdown Content
markdown = f"""
Hi There!

Joined Github **{years_joined}** years ago.

Since then I pushed **{total_commits}** commits, opened **{total_issues}** issues, submitted **{total_prs}** pull requests, received **{total_stars}** stars across **{total_personal_repos}** personal projects.

Most used languages across my projects:

{lang_badges}
"""

print("--- Generated Markdown ---")
print(markdown)

# 6. Write to README
with open("README.md", "r") as f:
    content = f.read()

start = ""
end = ""

if start in content and end in content:
    s_idx = content.find(start) + len(start)
    e_idx = content.find(end)
    new_content = content[:s_idx] + "\n" + markdown + "\n" + content[e_idx:]
    
    with open("README.md", "w") as f:
        f.write(new_content)
    print("README updated successfully.")
else:
    print("Markers not found in README.md")