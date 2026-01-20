import os
import requests
import datetime

# 1. SETUP
GITHUB_TOKEN = os.getenv("GH_TOKEN")
USERNAME = os.getenv("GITHUB_ACTOR")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# 2. QUERIES
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

# 3. GET DATA
print(f"Fetching data for {USERNAME}...")
user_data = run_query(user_query, {"login": USERNAME})["data"]["user"]
created_at = datetime.datetime.fromisoformat(user_data["createdAt"].replace("Z", "+00:00"))
now = datetime.datetime.now(datetime.timezone.utc)
years_joined = now.year - created_at.year

# 4. CALCULATE STATS (LIFETIME LOOP)
total_commits = 0
total_prs = 0
total_issues = 0
total_stars = 0
languages = {}
total_size = 0

# Count Repos & Languages
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

# Loop through every year since you joined to get accurate "5 year" stats
for year in range(created_at.year, now.year + 1):
    start = f"{year}-01-01T00:00:00Z"
    end = f"{year}-12-31T23:59:59Z"
    if year == created_at.year: start = user_data["createdAt"]
    if year == now.year: end = now.isoformat()
    
    print(f"Fetching year {year}...")
    data = run_query(contribution_query, {"login": USERNAME, "from": start, "to": end})["data"]["user"]["contributionsCollection"]
    total_commits += data["totalCommitContributions"] + data["restrictedContributionsCount"]
    total_prs += data["totalPullRequestContributions"]
    total_issues += data["totalIssueContributions"]

# 5. GENERATE BADGES
sorted_langs = sorted(languages.items(), key=lambda x: x[1]["size"], reverse=True)[:8]
badges = ""
for name, info in sorted_langs:
    pct = (info["size"] / total_size) * 100 if total_size > 0 else 0
    color = info["color"].replace("#", "") if info["color"] else "cccccc"
    safe_name = name.replace(" ", "%20").replace("-", "--")
    badges += f"![{name}](https://img.shields.io/static/v1?style=flat-square&label=%E2%A0%80&color=555&labelColor=%23{color}&message={safe_name}%EF%B8%B1{pct:.1f}%25)\n"

# 6. GENERATE FINAL TEXT
new_stats = f"""
Hi There!

Joined Github **{years_joined}** years ago.

Since then I pushed **{total_commits}** commits, opened **{total_issues}** issues, submitted **{total_prs}** pull requests, received **{total_stars}** stars across **{total_repos}** personal projects.

Most used languages across my projects:

{badges}
"""

# 7. UPDATE README (CLEAN SWAP)
with open("README.md", "r") as f:
    content = f.read()

start = ""
end = ""

# This logic forces a clean replacement
if start in content and end in content:
    pre = content.split(start)[0]
    post = content.split(end)[1]
    with open("README.md", "w") as f:
        f.write(pre + start + "\n" + new_stats + "\n" + end + post)
    print("Success!")
else:
    print("Error: Could not find markers in README.md")