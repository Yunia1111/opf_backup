"""
Launcher for the OPF Dashboard.
Executes the Streamlit application as a separate subprocess to ensure environment stability.
"""
import sys
import os
import subprocess

def main():
    print("🚀 Launching OPF Studio Dashboard...")

    # 1. Resolve absolute path to dashboard.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dashboard_path = os.path.join(current_dir, "dashboard.py")

    # 2. Launch command
    # Equivalent to: python -m streamlit run /path/to/dashboard.py
    cmd = [
        sys.executable, "-m", "streamlit", "run", dashboard_path,
        "--theme.base", "light",
        "--server.headless", "false",
    ]
    print("\n To stop dashboard, type Ctrl+C.")
    try:
        # 3. Run Streamlit as a subprocess
        # Blocks execution until the dashboard is closed or interrupted
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n Dashboard stopped by user (Ctrl+C). Exiting...")
        
    except Exception as e:
        print(f"Failed to launch dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()