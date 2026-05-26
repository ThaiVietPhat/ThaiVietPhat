import os
import requests
import json
import re

GITHUB_USERNAME = "ThaiVietPhat"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Mapping of topics to technical descriptions and badges
TOPIC_TECH_MAP = {
    "java": ("Java", "ED8B00", "openjdk", "Backend development using Java."),
    "spring-boot": ("Spring Boot", "6DB33F", "spring-boot", "Robust backend application using Spring Boot."),
    "spring-security": ("Spring Security", "6DB33F", "spring-security", "Secure authentication and authorization."),
    "microservices": ("Microservices", "E34F26", "spring", "Scalable distributed microservices architecture."),
    "kafka": ("Apache Kafka", "231F20", "apache-kafka", "Event-driven architecture and real-time messaging."),
    "redis": ("Redis", "DC382D", "redis", "High-performance caching and distributed sessions."),
    "docker": ("Docker", "2496ED", "docker", "Containerized deployment and environment consistency."),
    "kubernetes": ("Kubernetes", "326CE5", "kubernetes", "Automated container deployment and scaling."),
    "websocket": ("WebSocket", "010101", "socket.io", "Real-time bidirectional communication."),
    "jwt": ("JWT", "000000", "json-web-tokens", "Stateless authentication via JSON Web Tokens."),
    "mysql": ("MySQL", "4479A1", "mysql", "Relational database management."),
    "postgresql": ("PostgreSQL", "316192", "postgresql", "Advanced relational database management."),
    "mongodb": ("MongoDB", "4EA94B", "mongodb", "NoSQL document database."),
}

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def fetch_top_repositories():
    """Fetches the user's top repositories based on star count and updates."""
    print("Fetching top repositories...")
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos?sort=updated&per_page=100"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        print(f"Failed to fetch repositories: {response.status_code} - {response.text}")
        return []

    repos = response.json()
    top_repos = []

    # Filter out forks and self-repo
    for repo in repos:
        if not repo["fork"] and repo["name"] != GITHUB_USERNAME:
             top_repos.append(repo)

    # Sort by stars, then by updated_at
    top_repos.sort(key=lambda x: (x['stargazers_count'], x['updated_at']), reverse=True)
    return top_repos[:3]

def analyze_repo(repo):
    """Analyzes a repository to extract relevant tech descriptions."""
    print(f"Analyzing {repo['name']}...")
    topics = repo.get("topics", [])
    description = repo.get("description", "") or ""

    tech_stack = []
    added_techs = set()

    for topic in topics:
        if topic in TOPIC_TECH_MAP and topic not in added_techs:
             tech_stack.append(TOPIC_TECH_MAP[topic])
             added_techs.add(topic)

    # Fallback to scanning description for keywords if topics are sparse
    for key, val in TOPIC_TECH_MAP.items():
        if key not in added_techs and re.search(r'\b' + re.escape(key.replace('-', ' ')) + r'\b', description, re.IGNORECASE):
            tech_stack.append(val)
            added_techs.add(key)
        elif key not in added_techs and key in ['kafka', 'redis', 'docker', 'kubernetes', 'websocket', 'jwt', 'mysql', 'postgresql', 'mongodb'] and re.search(r'\b' + re.escape(key) + r'\b', description, re.IGNORECASE):
            tech_stack.append(val)
            added_techs.add(key)

    # Fallback to language if no recognized topics
    if not tech_stack and repo.get("language"):
        lang = repo["language"].lower()
        if lang in TOPIC_TECH_MAP and lang not in added_techs:
            tech_stack.append(TOPIC_TECH_MAP[lang])
            added_techs.add(lang)

    return tech_stack

def generate_markdown(repos):
    """Generates the Markdown content for the featured projects."""
    md_content = ""
    for repo in repos:
        tech_stack = analyze_repo(repo)

        name = repo["name"].replace("-", " ").title()
        description = repo.get("description") or "No description provided."
        url = repo["html_url"]

        md_content += f"### 💡 {name}\n\n"
        md_content += f"> **Status:** Active | **Stars:** ⭐ {repo['stargazers_count']}\n>\n"
        md_content += f"> {description}\n\n"

        if tech_stack:
            md_content += "<table>\n<tr>\n<th width=\"100%\">🛠️ Technical Highlights</th>\n</tr>\n<tr>\n<td valign=\"top\">\n\n"
            for tech_name, color, logo, tech_desc in tech_stack:
                md_content += f"- **{tech_name}:** {tech_desc}\n"
            md_content += "\n</td>\n</tr>\n</table>\n\n"

            md_content += "<p>\n"
            md_content += f"  <a href=\"{url}\">\n"
            md_content += f"    <img src=\"https://img.shields.io/badge/Source_Code-View_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white\" />\n"
            md_content += "  </a>\n"

            for tech_name, color, logo, _ in tech_stack[:3]: # Limit to 3 badges
                 encoded_name = tech_name.replace(" ", "_")
                 md_content += f"  <img src=\"https://img.shields.io/badge/{encoded_name}-{color}?style=for-the-badge&logo={logo}\" />\n"
            md_content += "</p>\n\n"
        else:
            md_content += "<p>\n"
            md_content += f"  <a href=\"{url}\">\n"
            md_content += f"    <img src=\"https://img.shields.io/badge/Source_Code-View_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white\" />\n"
            md_content += "  </a>\n"
            md_content += "</p>\n\n"

        md_content += "---\n\n"

    return md_content

def update_readme(md_content):
    """Updates the README.md file with the generated content."""
    readme_path = "README.md"
    try:
        with open(readme_path, "r") as f:
            readme_data = f.read()

        start_marker = "<!-- START_FEATURED_PROJECTS -->"
        end_marker = "<!-- END_FEATURED_PROJECTS -->"

        start_idx = readme_data.find(start_marker)
        end_idx = readme_data.find(end_marker)

        if start_idx != -1 and end_idx != -1:
            new_readme = (
                readme_data[:start_idx + len(start_marker)] + "\n\n" +
                md_content + "\n" +
                readme_data[end_idx:]
            )

            with open(readme_path, "w") as f:
                f.write(new_readme)
            print("Successfully updated README.md")
        else:
            print("Could not find start or end markers in README.md")
    except Exception as e:
        print(f"Error updating README.md: {e}")

if __name__ == "__main__":
    repos = fetch_top_repositories()
    md = generate_markdown(repos)
    update_readme(md)
