import os
import requests
import json
import re
import base64

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
    "python": ("Python", "3776AB", "python", "Scripting and automation using Python."),
    "javascript": ("JavaScript", "F7DF1E", "javascript", "Frontend and interactive web elements."),
    "typescript": ("TypeScript", "3178C6", "typescript", "Strongly typed scalable web applications."),
    "react": ("React", "61DAFB", "react", "Interactive user interfaces using React."),
    "aws": ("AWS", "FF9900", "amazon-aws", "Cloud deployment and scalable infrastructure."),
    "hibernate": ("Hibernate", "59666C", "hibernate", "Object-relational mapping and database access."),
    "junit": ("JUnit 5", "25A162", "junit5", "Automated unit testing and quality assurance."),
    "flyway": ("Flyway", "CC0200", "flyway", "Database migrations."),
    "kotlin": ("Kotlin", "7F52FF", "kotlin", "Modern backend development using Kotlin."),
    "html": ("HTML5", "E34F26", "html5", "Semantic markup language."),
    "css": ("CSS3", "1572B6", "css3", "Styling web applications.")
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


def fetch_repo_languages(repo_name):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/languages"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        return response.json()
    return {}


def fetch_file_content(repo_name, file_path):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo_name}/contents/{file_path}"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        file_data = response.json()
        if "content" in file_data:
            try:
                return base64.b64decode(file_data["content"]).decode('utf-8')
            except Exception as e:
                print(f"Error decoding {file_path}: {e}")
    return None

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


    # Fetch languages from GitHub API
    languages = fetch_repo_languages(repo["name"])
    for lang in languages.keys():
        lang_lower = lang.lower()
        if lang_lower in TOPIC_TECH_MAP and lang_lower not in added_techs:
            tech_stack.append(TOPIC_TECH_MAP[lang_lower])
            added_techs.add(lang_lower)



    # Scan config files for dependencies
    config_files = ["pom.xml", "build.gradle", "build.gradle.kts", "package.json"]
    for file_path in config_files:
        file_content = fetch_file_content(repo["name"], file_path)
        if file_content:
            for key, val in TOPIC_TECH_MAP.items():
                if key not in added_techs and re.search(r'\b' + re.escape(key) + r'\b', file_content, re.IGNORECASE):
                    tech_stack.append(val)
                    added_techs.add(key)
                elif key == "spring-boot" and "spring-boot" not in added_techs and "spring-boot" in file_content:
                    tech_stack.append(val)
                    added_techs.add(key)
                elif key == "jwt" and "jwt" not in added_techs and ("jsonwebtoken" in file_content or "jwt" in file_content):
                    tech_stack.append(val)
                    added_techs.add(key)
                elif key == "redis" and "redis" not in added_techs and ("spring-boot-starter-data-redis" in file_content or "redis" in file_content):
                     tech_stack.append(val)
                     added_techs.add(key)
                elif key == "kafka" and "kafka" not in added_techs and ("spring-kafka" in file_content or "kafka" in file_content):
                     tech_stack.append(val)
                     added_techs.add(key)

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
