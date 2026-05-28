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

import base64

def get_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def get_repo_languages(repo_name):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        return response.json()
    return {}

def get_file_content(repo_name, filepath):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{filepath}"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict) and "content" in data:
            try:
                return base64.b64decode(data["content"]).decode("utf-8")
            except Exception:
                pass
    return None

def check_path_exists(repo_name, filepath):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{filepath}"
    response = requests.get(url, headers=get_headers())
    return response.status_code == 200

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
    repo_name = repo["name"]
    topics = repo.get("topics", [])
    description = repo.get("description", "") or ""

    tech_stack = []
    added_techs = set()

    def add_tech(key):
        if key in TOPIC_TECH_MAP and key not in added_techs:
            tech_stack.append(TOPIC_TECH_MAP[key])
            added_techs.add(key)

    # 1. Topics
    for topic in topics:
        add_tech(topic)

    # 2. Languages API
    languages = get_repo_languages(repo_name)
    for lang in languages:
        add_tech(lang.lower())

    # 3. Dependency files
    pom_xml = get_file_content(repo_name, "pom.xml")
    if pom_xml:
        add_tech("java")
        if "spring-boot" in pom_xml: add_tech("spring-boot")
        if "spring-cloud" in pom_xml: add_tech("microservices")
        if "spring-kafka" in pom_xml or "kafka-clients" in pom_xml: add_tech("kafka")
        if "spring-data-redis" in pom_xml or "jedis" in pom_xml: add_tech("redis")
        if "jjwt" in pom_xml or "java-jwt" in pom_xml: add_tech("jwt")
        if "mysql-connector" in pom_xml: add_tech("mysql")
        if "postgresql" in pom_xml: add_tech("postgresql")
        if "spring-data-mongodb" in pom_xml: add_tech("mongodb")
        if "spring-security" in pom_xml: add_tech("spring-security")
        if "spring-boot-starter-websocket" in pom_xml: add_tech("websocket")

    package_json = get_file_content(repo_name, "package.json")
    if package_json:
        if "jsonwebtoken" in package_json: add_tech("jwt")
        if "socket.io" in package_json or "ws" in package_json: add_tech("websocket")
        if "redis" in package_json or "ioredis" in package_json: add_tech("redis")
        if "kafkajs" in package_json: add_tech("kafka")
        if "mysql" in package_json or "mysql2" in package_json: add_tech("mysql")
        if "pg" in package_json: add_tech("postgresql")
        if "mongodb" in package_json or "mongoose" in package_json: add_tech("mongodb")

    build_gradle = get_file_content(repo_name, "build.gradle")
    if build_gradle:
        add_tech("java")
        if "spring-boot" in build_gradle: add_tech("spring-boot")
        if "spring-security" in build_gradle: add_tech("spring-security")

    dockerfile = get_file_content(repo_name, "Dockerfile")
    if dockerfile or get_file_content(repo_name, "docker-compose.yml"):
        add_tech("docker")

    # Kubernetes manifests or helm charts check could be complex,
    # but we check if typical k8s directory exists
    if check_path_exists(repo_name, "k8s") or check_path_exists(repo_name, "kubernetes"):
        add_tech("kubernetes")

    # 4. Fallback to scanning description for keywords
    for key, val in TOPIC_TECH_MAP.items():
        if key not in added_techs and re.search(r'\b' + re.escape(key.replace('-', ' ')) + r'\b', description, re.IGNORECASE):
            add_tech(key)
        elif key not in added_techs and key in ['kafka', 'redis', 'docker', 'kubernetes', 'websocket', 'jwt', 'mysql', 'postgresql', 'mongodb'] and re.search(r'\b' + re.escape(key) + r'\b', description, re.IGNORECASE):
            add_tech(key)

    # 5. Fallback to repository language property
    if not tech_stack and repo.get("language"):
        add_tech(repo["language"].lower())

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
