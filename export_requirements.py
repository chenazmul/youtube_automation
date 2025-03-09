import subprocess
import sys
import os

def export_requirements():
    """
    ইনস্টল করা সব পাইথন লাইব্রেরি requirements.txt ফাইলে এক্সপোর্ট করা
    """
    try:
        print("Exporting installed Python packages to requirements.txt...")
        
        # pip freeze কমান্ড চালিয়ে ইনস্টল করা সব লাইব্রেরি পাওয়া
        result = subprocess.run([sys.executable, "-m", "pip", "freeze"], 
                              capture_output=True, text=True, check=True)
        
        requirements = result.stdout
        
        # requirements.txt ফাইলে লেখা
        with open("requirements.txt", "w") as f:
            f.write(requirements)
        
        # ফাইলের লোকেশন খুঁজে বের করা
        file_path = os.path.abspath("requirements.txt")
        
        print(f"Success! Total {len(requirements.splitlines())} packages exported.")
        print(f"File saved at: {file_path}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error running pip freeze: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    export_requirements()
    input("Press Enter to exit...")