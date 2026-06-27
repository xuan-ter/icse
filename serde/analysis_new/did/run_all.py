import os
import subprocess
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = [
    "analyze_interaction.py",
    "classify_and_plot.py",
    "plot_coupling.py",
    "plot_knowledge_graph.py",
]


def main():
    for script_name in SCRIPTS:
        script_path = os.path.join(BASE_DIR, script_name)
        print(f"Running {script_name}...")
        subprocess.run([sys.executable, script_path], check=True)

    print("All DiD analysis steps completed.")


if __name__ == "__main__":
    main()
