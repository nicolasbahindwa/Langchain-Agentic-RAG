from setuptools import setup, find_packages

setup(
    name="agentic-rag",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langgraph",
        "langchain",
        "pydantic",
        "typing-extensions",
        # Add other dependencies here
    ],
    python_requires=">=3.8",
)