# GitHub Archive Live Dashboard
# A complete real-time data pipeline for GitHub activity analysis

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import redis
from collections import defaultdict, Counter
import threading
import queue
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GitHubStreamProcessor:
    """Processes GitHub Archive data stream and computes real-time analytics"""

    def __init__(self):
        # In-memory storage for demo (in production, use Redis/PostgreSQL)
        self.language_stats = Counter()
        self.repo_stats = Counter()
        self.event_stats = Counter()
        self.user_stats = Counter()
        self.hourly_stats = defaultdict(lambda: defaultdict(int))

        # Data queues for real-time updates
        self.data_queue = queue.Queue(maxsize=1000)
        self.is_processing = False

        # Cache for dashboard
        self.cache = {
            'last_updated': datetime.now(),
            'trending_repos': [],
            'language_popularity': {},
            'event_timeline': [],
            'top_users': [],
            'total_events': 0
        }

    def process_github_event(self, event: Dict):
        """Process a single GitHub event and update statistics"""
        try:
            event_type = event.get('type', 'Unknown')
            repo = event.get('repo', {})
            repo_name = repo.get('name', 'unknown/unknown')
            actor = event.get('actor', {})
            username = actor.get('login', 'unknown')

            # Update event statistics
            self.event_stats[event_type] += 1
            self.repo_stats[repo_name] += 1
            self.user_stats[username] += 1

            # Extract language information from payload
            payload = event.get('payload', {})

            # For PushEvent, try to get language from commits
            if event_type == 'PushEvent' and 'commits' in payload:
                # In real implementation, you'd need to fetch repo details for language
                # For demo, we'll simulate language detection
                language = self._simulate_language_detection(repo_name)
                if language:
                    self.language_stats[language] += 1

            # For other events, simulate language based on repo patterns
            elif event_type in ['WatchEvent', 'ForkEvent', 'IssuesEvent']:
                language = self._simulate_language_detection(repo_name)
                if language:
                    self.language_stats[language] += 1

            # Update hourly statistics
            current_hour = datetime.now().strftime('%H:00')
            self.hourly_stats[current_hour][event_type] += 1

            return True

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return False

    def _simulate_language_detection(self, repo_name: str) -> Optional[str]:
        """Simulate language detection based on repo naming patterns"""
        # In production, you'd fetch repo details via GitHub API
        # This is a simulation for demo purposes
        patterns = {
            'python': ['.py', 'django', 'flask', 'fastapi', 'ml', 'ai', 'data'],
            'javascript': ['.js', 'react', 'vue', 'node', 'npm', 'web'],
            'java': ['.java', 'spring', 'maven', 'android'],
            'go': ['.go', 'golang', 'gin', 'fiber'],
            'rust': ['.rs', 'cargo', 'actix'],
            'typescript': ['.ts', 'angular', 'nest'],
            'c++': ['.cpp', '.cc', 'cmake'],
            'c#': ['.cs', 'dotnet', 'asp'],
            'php': ['.php', 'laravel', 'symfony'],
            'ruby': ['.rb', 'rails', 'gem']
        }

        repo_lower = repo_name.lower()
        for language, keywords in patterns.items():
            if any(keyword in repo_lower for keyword in keywords):
                return language

        # Default distribution for unknown repos
        import random
        languages = ['python', 'javascript', 'java', 'typescript', 'go', 'rust', 'c++']
        return random.choice(languages) if random.random() > 0.3 else None

    def update_cache(self):
        """Update dashboard cache with latest statistics"""
        self.cache.update({
            'last_updated': datetime.now(),
            'trending_repos': self.repo_stats.most_common(10),
            'language_popularity': dict(self.language_stats.most_common(10)),
            'top_users': self.user_stats.most_common(10),
            'total_events': sum(self.event_stats.values()),
            'event_breakdown': dict(self.event_stats.most_common()),
            'hourly_stats': dict(self.hourly_stats)
        })

    def generate_sample_events(self, count: int = 50):
        """Generate sample GitHub events for demo purposes"""
        import random

        event_types = ['PushEvent', 'WatchEvent', 'ForkEvent', 'IssuesEvent',
                       'PullRequestEvent', 'CreateEvent', 'DeleteEvent']

        sample_repos = [
            'microsoft/vscode', 'facebook/react', 'tensorflow/tensorflow',
            'pytorch/pytorch', 'kubernetes/kubernetes', 'golang/go',
            'rust-lang/rust', 'python/cpython', 'nodejs/node',
            'angular/angular', 'vuejs/vue', 'laravel/laravel'
        ]

        sample_users = [f'developer_{i}' for i in range(1, 21)]

        events = []
        for _ in range(count):
            event = {
                'type': random.choice(event_types),
                'repo': {'name': random.choice(sample_repos)},
                'actor': {'login': random.choice(sample_users)},
                'created_at': datetime.now().isoformat(),
                'payload': {}
            }
            events.append(event)
            self.process_github_event(event)

        self.update_cache()
        return events


# Global processor instance
processor = GitHubStreamProcessor()


def create_dashboard():
    """Create the Streamlit dashboard"""

    st.set_page_config(
        page_title="GitHub Archive Live Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric { 
        background-color: #16c3f7;
        padding: 1rem;
         color: white;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    
/* Change delta (counter) color to #2260bd */
[data-testid="stMetricDelta"] svg {
    color: #2260bd !important;
}

/* Optional: Also style the delta text */
[data-testid="stMetricDelta"] div {
    color: #2260bd !important;
    font-weight: bold;
}
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown('<h1 class="main-header">🚀 GitHub Archive Live Dashboard</h1>',
                unsafe_allow_html=True)

    st.markdown("---")

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Dashboard Controls")
        # GitHub link aligned to top left
        st.markdown(
            """
            <style>
            .top-github-link {
                color: #2260bd;
                font-weight: 600;
                text-decoration: none;
                position: relative;
                transition: all 0.3s ease;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 12px;  /* Make it smaller - was 14px by default */
            }
            .top-github-link:hover {
                color: #ff6b6b;
            }
            .top-github-link:hover::after {
                content: "Visit my GitHub";
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background: #333;
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                white-space: nowrap;
                margin-bottom: 5px;
            }
            </style>
   
            <div style='text-align: left; margin-top: -85px; margin-bottom: 30px; margin-left: 0px;'>
                <a href="https://github.com/IamIremIdil" target="_blank" class="top-github-link">
                    🐙 My GitHub
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Auto Refresh", value=True)
        refresh_interval = st.slider("Refresh Interval (seconds)", 1, 30, 5)

        # Manual refresh button
        if st.button("🔄 Refresh Data"):
            processor.generate_sample_events(50)
            st.success("Data refreshed!")

        # Generate sample data button
        if st.button("📊 Generate Sample Data"):
            processor.generate_sample_events(100)
            st.success("Sample data generated!")

        st.markdown("---")
        st.markdown("### 📈 System Status")
        st.info(f"Last Updated: {processor.cache['last_updated'].strftime('%H:%M:%S')}")
        st.info(f"Total Events: {processor.cache['total_events']:,}")

    # Main dashboard content
    if processor.cache['total_events'] == 0:
        st.warning("No data available. Click 'Generate Sample Data' to start!")
        return

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🎯 Total Events",
            value=f"{processor.cache['total_events']:,}",
            delta="+50" if processor.cache['total_events'] > 50 else None
        )

    with col2:
        top_language = max(processor.cache['language_popularity'],
                           key=processor.cache['language_popularity'].get) if processor.cache[
            'language_popularity'] else "N/A"
        st.metric(
            label="🔥 Top Language",
            value=top_language,
            delta=f"{processor.cache['language_popularity'].get(top_language, 0)} events"
        )

    with col3:
        trending_repo = processor.cache['trending_repos'][0][0] if processor.cache['trending_repos'] else "N/A"
        st.metric(
            label="⭐ Trending Repo",
            value=trending_repo.split('/')[-1] if '/' in trending_repo else trending_repo,
            delta=f"{processor.cache['trending_repos'][0][1] if processor.cache['trending_repos'] else 0} events"
        )

    with col4:
        top_user = processor.cache['top_users'][0][0] if processor.cache['top_users'] else "N/A"
        st.metric(
            label="👑 Top User",
            value=top_user,
            delta=f"{processor.cache['top_users'][0][1] if processor.cache['top_users'] else 0} events"
        )

    st.markdown("---")

    # Charts row 1
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Language Popularity")
        if processor.cache['language_popularity']:
            lang_df = pd.DataFrame(
                list(processor.cache['language_popularity'].items()),
                columns=['Language', 'Events']
            )
            fig = px.bar(
                lang_df,
                x='Language',
                y='Events',
                title="Most Active Programming Languages",
                color='Events',
                color_continuous_scale='viridis'
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No language data available yet.")

    with col2:
        st.subheader("🏆 Trending Repositories")
        if processor.cache['trending_repos']:
            repo_df = pd.DataFrame(
                processor.cache['trending_repos'],
                columns=['Repository', 'Events']
            )
            repo_df['Repository'] = repo_df['Repository'].str.split('/').str[-1]

            fig = px.pie(
                repo_df.head(8),
                values='Events',
                names='Repository',
                title="Most Active Repositories"
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No repository data available yet.")

    # Charts row 2
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Event Types Breakdown")
        if processor.cache.get('event_breakdown'):
            event_df = pd.DataFrame(
                list(processor.cache['event_breakdown'].items()),
                columns=['Event Type', 'Count']
            )
            fig = px.bar(
                event_df,
                x='Count',
                y='Event Type',
                title="GitHub Event Types Distribution",
                color='Count',
                color_continuous_scale='plasma',
                orientation='h'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No event data available yet.")

    with col2:
        st.subheader("👥 Top Active Users")
        if processor.cache['top_users']:
            user_df = pd.DataFrame(
                processor.cache['top_users'][:10],
                columns=['Username', 'Activity']
            )
            fig = px.scatter(
                user_df,
                x='Username',
                y='Activity',
                size='Activity',
                title="Most Active GitHub Users",
                color='Activity',
                color_continuous_scale='blues'
            )
            fig.update_layout(height=400)
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No user activity data available yet.")

    # Data tables section
    st.markdown("---")
    st.subheader("📋 Detailed Statistics")

    tab1, tab2, tab3 = st.tabs(["🏆 Top Repositories", "💻 Language Stats", "👤 User Activity"])

    with tab1:
        if processor.cache['trending_repos']:
            repo_table_df = pd.DataFrame(
                processor.cache['trending_repos'],
                columns=['Repository', 'Events']
            )
            repo_table_df.index = range(1, len(repo_table_df) + 1)
            st.dataframe(repo_table_df, use_container_width=True)
        else:
            st.info("No repository data available.")

    with tab2:
        if processor.cache['language_popularity']:
            lang_table_df = pd.DataFrame(
                list(processor.cache['language_popularity'].items()),
                columns=['Programming Language', 'Total Events']
            )
            lang_table_df.index = range(1, len(lang_table_df) + 1)
            st.dataframe(lang_table_df, use_container_width=True)
        else:
            st.info("No language data available.")

    with tab3:
        if processor.cache['top_users']:
            user_table_df = pd.DataFrame(
                processor.cache['top_users'],
                columns=['Username', 'Total Activity']
            )
            user_table_df.index = range(1, len(user_table_df) + 1)
            st.dataframe(user_table_df, use_container_width=True)
        else:
            st.info("No user activity data available.")
    # Professional footer with tooltip
    footer_html = """
    <style>
    .footer {
        text-align: center;
        color: #666666;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 14px;
        margin-top: 3rem;
        padding: 1.5rem;
        border-top: 1px solid #e0e0e0;
    }
    .github-link {
        color: #2260bd;
        font-weight: 600;
        text-decoration: none;
        position: relative;
        transition: all 0.3s ease;
    }
    .github-link:hover {
        color: #ff6b6b;
    }
    .github-link:hover::after {
        content: "Visit my GitHub";
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
    }
    </style>

    <div class="footer">
        Crafted with ❤️ by 
        <a href="https://github.com/IamIremIdil" target="_blank" class="github-link">iro</a> 
        © 2025
    </div>
    """

    st.markdown("---")
    st.markdown(footer_html, unsafe_allow_html=True)

    # Auto-refresh functionality
    if auto_refresh:
        time.sleep(refresh_interval)
        processor.generate_sample_events(20)  # Add some new data
        st.rerun()


# Production Components (for reference)
class ProductionComponents:
    """
    Production-ready components that would be used in a real deployment.
    These are reference implementations showing the full architecture.
    """

    @staticmethod
    def kafka_producer_example():
        """Example Kafka producer for GitHub events"""
        kafka_code = '''
from kafka import KafkaProducer
import json
import requests

class GitHubEventProducer:
    def __init__(self, kafka_servers=['localhost:9092']):
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )

    async def stream_github_events(self):
        """Stream real GitHub events to Kafka"""
        url = "https://stream.gharchive.org/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                async for line in response.content:
                    try:
                        event = json.loads(line)
                        self.producer.send('github-events', event)
                    except json.JSONDecodeError:
                        continue
        '''
        return kafka_code

    @staticmethod
    def fastapi_backend_example():
        """Example FastAPI backend"""
        fastapi_code = '''
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis

app = FastAPI(title="GitHub Analytics API")
redis_client = redis.Redis(host='localhost', port=6379, db=0)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/trending/repos")
async def get_trending_repos(limit: int = 10):
    """Get trending repositories"""
    # Query Redis/PostgreSQL for trending repos
    return {"trending_repos": []}

@app.get("/api/languages/popularity")
async def get_language_popularity():
    """Get programming language popularity"""
    # Query database for language statistics
    return {"languages": {}}
        '''
        return fastapi_code

    @staticmethod
    def docker_compose_example():
        """Example Docker Compose configuration"""
        docker_compose = '''
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: github_analytics
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"

  api:
    build: ./api
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - postgres

  dashboard:
    build: ./dashboard
    ports:
      - "8501:8501"
    depends_on:
      - api
        '''
        return docker_compose


if __name__ == "__main__":
    # Initialize with some sample data
    processor.generate_sample_events(100)

    # Run the dashboard
    create_dashboard()
