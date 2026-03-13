from setuptools import setup

setup(
    name="personal-assistant-snakecharmers",
    version="0.1.0",
    # Вказуємо окремі файли, бо вони лежать у корені, а не в папці
    py_modules=["cli", "contacts", "notebook", "utils"], 
    install_requires=[
        "prompt_toolkit==3.0.52",
        "rich==14.3.3",
    ],
    entry_points={
        'console_scripts': [
            'helper-bot=cli:main',
        ],
    },
    author="SnakeCharmers Team",
    description="CLI Personal Assistant with Address Book and Notebook",
    python_requires='>=3.7',
)
