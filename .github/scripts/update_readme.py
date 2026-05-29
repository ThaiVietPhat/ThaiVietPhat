import os
import requests
import json
import re
import base64

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

class GitHubClient:
    def __init__(self, username, token=None):
        self.username = username
        self.token = token
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None

    def get_repo_languages(self, repo_name):
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/languages"
        response = self.get(url)
        return response.json() if response else {}

    def get_file_content(self, repo_name, filepath):
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{filepath}"
        response = self.get(url)
        if response:
            data = response.json()
            if isinstance(data, dict) and "content" in data:
                try:
                    return base64.b64decode(data["content"]).decode("utf-8")
                except Exception:
                    pass
        return None

    def check_path_exists(self, repo_name, filepath):
        url = f"https://api.github.com/repos/{self.username}/{repo_name}/contents/{filepath}"
        response = self.get(url)
        return response is not None

    def fetch_top_repositories(self):
        print("Fetching top repositories...")
        url = f"https://api.github.com/users/{self.username}/repos?sort=updated&per_page=100"
        response = self.get(url)
        if not response:
            return []

        repos = response.json()
        top_repos = []
        for repo in repos:
            if not repo["fork"] and repo["name"] != self.username:
                 top_repos.append(repo)
        top_repos.sort(key=lambda x: (x['stargazers_count'], x['updated_at']), reverse=True)
        return top_repos[:3]

class TechAnalyzer:
    def __init__(self, github_client):
        self.github_client = github_client

    def analyze_repo(self, repo):
        repo_name = repo["name"]
        print(f"Analyzing {repo_name}...")
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
        languages = self.github_client.get_repo_languages(repo_name)
        for lang in languages:
            add_tech(lang.lower())

        # 3. Dependency files
        pom_xml = self.github_client.get_file_content(repo_name, "pom.xml")
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

        package_json = self.github_client.get_file_content(repo_name, "package.json")
        if package_json:
            if "jsonwebtoken" in package_json: add_tech("jwt")
            if "socket.io" in package_json or "ws" in package_json: add_tech("websocket")
            if "redis" in package_json or "ioredis" in package_json: add_tech("redis")
            if "kafkajs" in package_json: add_tech("kafka")
            if "mysql" in package_json or "mysql2" in package_json: add_tech("mysql")
            if "pg" in package_json: add_tech("postgresql")
            if "mongodb" in package_json or "mongoose" in package_json: add_tech("mongodb")

        build_gradle = self.github_client.get_file_content(repo_name, "build.gradle")
        if build_gradle:
            add_tech("java")
            if "spring-boot" in build_gradle: add_tech("spring-boot")
            if "spring-security" in build_gradle: add_tech("spring-security")

        dockerfile = self.github_client.get_file_content(repo_name, "Dockerfile")
        if dockerfile or self.github_client.get_file_content(repo_name, "docker-compose.yml"):
            add_tech("docker")

        if self.github_client.check_path_exists(repo_name, "k8s") or self.github_client.check_path_exists(repo_name, "kubernetes"):
            add_tech("kubernetes")

        # 4. Fallback scanning
        for key in TOPIC_TECH_MAP.keys():
            if key not in added_techs and re.search(r'\b' + re.escape(key.replace('-', ' ')) + r'\b', description, re.IGNORECASE):
                add_tech(key)
            elif key not in added_techs and key in ['kafka', 'redis', 'docker', 'kubernetes', 'websocket', 'jwt', 'mysql', 'postgresql', 'mongodb'] and re.search(r'\b' + re.escape(key) + r'\b', description, re.IGNORECASE):
                add_tech(key)

        # 5. Language fallback
        if not tech_stack and repo.get("language"):
            add_tech(repo["language"].lower())

        return tech_stack

class MarkdownGenerator:
    def generate(self, repos, analyzer):
        md_content = ""
        for repo in repos:
            tech_stack = analyzer.analyze_repo(repo)
            name = repo["name"].replace("-", " ").title()
            description = repo.get("description") or "No description provided."
            url = repo["html_url"]
            stars = repo['stargazers_count']

            # Modern Header
            md_content += f"### 💡 {name}\n\n"
            md_content += f"> **Status:** Active | **Stars:** ⭐ {stars}\n>\n"
            md_content += f"> {description}\n\n"

            if tech_stack:
                # Use Details/Summary for a cleaner look
                md_content += "<details>\n"
                md_content += "<summary><b>🛠️ Technical Highlights & Stack</b></summary>\n<br>\n\n"

                md_content += "<table>\n"
                md_content += "<tr>\n"
                md_content += "<th width=\"30%\">Technology</th>\n"
                md_content += "<th width=\"70%\">Implementation Details</th>\n"
                md_content += "</tr>\n"

                for tech_name, color, logo, tech_desc in tech_stack:
                    encoded_name = tech_name.replace(" ", "_").replace("-", "_")
                    badge = f"<img src=\"https://img.shields.io/badge/{encoded_name}-{color}?style=flat-square&logo={logo}&logoColor=white\" alt=\"{tech_name}\" />"
                    md_content += "<tr>\n"
                    md_content += f"<td align=\"center\">{badge}</td>\n"
                    md_content += f"<td>{tech_desc}</td>\n"
                    md_content += "</tr>\n"

                md_content += "</table>\n\n"
                md_content += "</details>\n\n"

            # Footer with Quick Links and Top Badges
            md_content += "<p>\n"
            md_content += f"  <a href=\"{url}\">\n"
            md_content += f"    <img src=\"https://img.shields.io/badge/Source_Code-View_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white\" />\n"
            md_content += "  </a>\n"

            if tech_stack:
                 for tech_name, color, logo, _ in tech_stack[:3]: # Limit to top 3 badges
                      encoded_name = tech_name.replace(" ", "_")
                      md_content += f"  <img src=\"https://img.shields.io/badge/{encoded_name}-{color}?style=for-the-badge&logo={logo}\" />\n"

            md_content += "</p>\n\n"
            md_content += "---\n\n"

        return md_content

class ReadmeUpdater:
    def __init__(self, filepath="README.md"):
        self.filepath = filepath

    def update(self, md_content):
        try:
            with open(self.filepath, "r") as f:
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

                with open(self.filepath, "w") as f:
                    f.write(new_readme)
                print(f"Successfully updated {self.filepath}")
            else:
                print(f"Could not find start or end markers in {self.filepath}")
        except Exception as e:
            print(f"Error updating {self.filepath}: {e}")

if __name__ == "__main__":
    username = "ThaiVietPhat"
    token = os.environ.get("GITHUB_TOKEN")

    client = GitHubClient(username, token)
    analyzer = TechAnalyzer(client)
    generator = MarkdownGenerator()
    updater = ReadmeUpdater()

    repos = client.fetch_top_repositories()
    if repos:
        md = generator.generate(repos, analyzer)
        updater.update(md)
    else:
        print("No repositories found to process.")
