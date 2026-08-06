from setuptools import find_packages, setup


setup(
    name="predicate",
    version="0.1.0",
    description="AI readiness certification SDK and DataHub integration reference implementation.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    entry_points={"console_scripts": [
        "predicate=context_gradient.cli:main",
        "context-gradient=context_gradient.cli:main",
        "predicate-review=predicate.review:main",
        "predicate-mcp=predicate.mcp_server:main",
        "predicate-doctor=predicate.doctor:main",
        "predicate-skill=context_gradient.skill:main",
        "predicate-datahub-mcp-probe=predicate.datahub_mcp_probe:main",
    ]},
)
